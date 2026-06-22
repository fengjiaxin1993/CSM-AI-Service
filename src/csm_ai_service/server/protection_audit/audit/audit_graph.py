import json
import operator
import threading
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from pydantic import BaseModel
from typing import List, Annotated

from csm_ai_service.server.protection_audit.audit.model import AuditRule, RuleAuditResult
from csm_ai_service.server.utils import get_ChatOpenAI, fix_llm_json_output
from csm_ai_service.settings import Settings


# ====================== 全局配置：LLM最大并发控制 ======================
llm_semaphore = threading.Semaphore(Settings.basic_settings.MAX_CONCURRENT_AUDIT_LLM)  # 全局信号量，全任务共享
executor = ThreadPoolExecutor(max_workers=Settings.basic_settings.MAX_CONCURRENT_AUDIT_LLM)  # 线程池和并发对齐



class AuditState(BaseModel):
    contract_id: int = 0
    contract_markdown_json: dict
    rule_list: List[AuditRule]
    single_rule_results: Annotated[List[RuleAuditResult], operator.add] = []
    final_report: str


# ====================== LLM实例 ======================
llm = get_ChatOpenAI(
            model_name=Settings.model_settings.DEFAULT_LLM_MODEL,
            temperature=Settings.model_settings.TEMPERATURE,
            max_tokens=Settings.model_settings.MAX_TOKENS,
            callbacks=[],

        )


# 获取相关文件内容
def get_related_text(contract_json: dict, chapter_list: List[str]):
    res = []
    doc_ids = []
    for chapter in chapter_list:
        for item_dic in contract_json["structure_json_result"]:
            item_title = item_dic["title"]
            if chapter in item_title:
                res.append(item_dic["text"])
                doc_ids.append(item_dic["doc_id"])
    return "\n---\n".join(res), doc_ids


# ====================== 内部：单规则真实LLM调用（被限流） ======================
def llm_audit_single(rule: AuditRule, contract_markdown_json: dict, contract_id: int = 0) -> RuleAuditResult:
    """被信号量限流的真实LLM请求函数"""
    related_text, doc_ids = get_related_text(contract_markdown_json, rule.chapter_keywords)

    with llm_semaphore:  # 进入自动占用令牌，超出MAX则阻塞排队
        prompt = f"""
请基于合同内容和审计规则做合规审查，合同正文中可能有markdown格式的表格数据,只返回JSON，禁止多余内容。
【合同相关内容】
{related_text}
【审计规则名称】{rule.name}
【审计规则描述】{rule.description}
【规则判定逻辑】{rule.judge_logic}

请按照以下JSON格式输出你的判断结果（只输出JSON，不要有其他内容）：
{{{{
    "is_compliant": true/false,
    "conclusion": "一句话结论",
    "reasoning": "详细的判断理由和解释"
    "origin_text": "从原文中找出相关的内容,一定是合同相关内容中的原文"
}}}}
"""
        resp = llm.invoke(prompt)
        res_dict = fix_llm_json_output(resp.content)
        return RuleAuditResult(
            contract_id=contract_id,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_description=rule.description,
            rule_judge_logic=rule.judge_logic,
            is_compliant=res_dict["is_compliant"],
            conclusion=res_dict["conclusion"],
            reasoning=res_dict["reasoning"],
            related_text=related_text,
            origin_text=res_dict["origin_text"],
            related_chapters=rule.chapter_keywords,
            related_doc_ids=doc_ids
        )


# ====================== LangGraph节点 ======================
def split_audit_tasks(state: AuditState):
    """条件路由函数：返回Send列表做并行fan-out（必须在conditional_edges中使用）"""
    return [
        Send("single_rule_audit", {"rule": rule, "contract_markdown_json": state.contract_markdown_json, "contract_id": state.contract_id})
        for rule in state.rule_list
    ]


def single_rule_audit(data: dict):
    """LangGraph子节点：提交任务到受限线程池"""
    rule: AuditRule = data["rule"]
    contract_markdown_json = data["contract_markdown_json"]
    contract_id = data.get("contract_id", 0)
    # 提交到带并发上限的线程池执行LLM
    future = executor.submit(llm_audit_single, rule, contract_markdown_json, contract_id)
    result = future.result()
    return {"single_rule_results": [result]}


def generate_final_report(state: AuditState):
    results = state.single_rule_results
    ok = [r for r in results if r.is_compliant]
    no_ok = [r for r in results if not r.is_compliant]

    report = f"""
===== 合同审计汇总报告 =====
总审计规则数量：{len(results)}
合规项：{len(ok)}项
不合规项：{len(no_ok)}项

"""
    if len(no_ok) > 0:
        report += "不合规清单如下：\n"
        for item in no_ok:
            report += f"\n【{item.rule_name}】\n原文：{item.related_text}\n原因：{item.reasoning}\n"

    return {"final_report": report}


# ====================== 构建Graph ======================
def create_graph():
    builder = StateGraph(AuditState)
    builder.add_node("single_rule_audit", single_rule_audit)
    builder.add_node("generate_final_report", generate_final_report)

    builder.add_conditional_edges(START, split_audit_tasks)
    builder.add_edge("single_rule_audit", "generate_final_report")
    builder.add_edge("generate_final_report", END)

    graph = builder.compile()
    return graph

GLOBAL_AUDIT_GRAPH = create_graph()

