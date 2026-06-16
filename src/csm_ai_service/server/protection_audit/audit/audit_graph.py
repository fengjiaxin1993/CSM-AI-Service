import json
import operator
import threading
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from pydantic import BaseModel
from typing import List, Annotated

from csm_ai_service.server.protection_audit.audit.model import AuditRule, RuleAuditResult
from csm_ai_service.server.utils import get_ChatOpenAI
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
请基于合同内容和审计规则做合规审查，只返回JSON，禁止多余内容。
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
    "origin_text": "从原文中找出相关的内容,一定是原文中的内容"
}}}}
"""
        resp = llm.invoke(prompt)
        res_dict = json.loads(resp.content)
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

#
# # ====================== 测试 ======================
# if __name__ == "__main__":
#     contract_json = {
#         "structure_json_result": [
#             {
#                 "title": "1.总则",
#                 "text": "# 1.总则  \n为保障草台第一分散式风电场电力监控系统网络安全，依据《中华人民共和国网络安全法》、《中华人民共和国密码法》、《电力监控系统安全防护规定》（发改委第27号）、《电力监控系统安全防护总体方案》（国能安全〔2015）36号）等国家、行业有关法律、法规，结合现场实际情况，制定本方案。 调-20  \n草台第一分散式风电场电力监控系统的防护目标是抵御黑客、病毒、恶意代码等通过各种形式对变电站电力监控系统发起的恶意破坏和攻击，以及其它非法操作，防止变电站电力监控系统瘫痪和失控，及由此导致的电站一次系统事故。",
#                 "doc_id": "doc_0"
#             },
#             {
#                 "title": "2.系统概况",
#                 "text": "# 2.系统概况  \n草台第一分散式风电场位于中卫市沙坡头区永康镇，场址地理位置坐标：经度(东经)105°3083′，纬度(北纬)37°3042′，总装机容量40MWp。通过单回35kV出线与草台110kV变电站相连，由中卫地调调管。电力监控系统采用四方变电站监控系统，由服务器、工作站、各类二次设备、网络设备、时钟同步装置、网络安全防护设备、安全操作系统、数据库等软硬件组成。 发",
#                 "doc_id": "doc_1"
#             },
#             {
#                 "title": "3.等保测评及安全防护评估",
#                 "text": "# 3.等保测评及安全防护评估  \n草台第一分散式风电场电力监控系统依据《电力行业信息系统等级保护定级工作指导意见》（国能综通安全〔2022）71号），安全保护等级定级为二级，委托专业机构每两年开展一次网络安全等级保护测评和网络安全风险评估。",
#                 "doc_id": "doc_2"
#             },
#             {
#                 "title": "4.安全防护实施方案",
#                 "text": "# 4.安全防护实施方案",
#                 "doc_id": "doc_3"
#             },
#             {
#                 "title": "4.1.安全分区",
#                 "text": "# 4.1.安全分区  \n草台第一分散式风电场开关站监控系统主要业务系统及设备有：场站监控系统、AGC/AVC控制系统、继电保护装置、快速频率响应装置、网络安全监测装置、故障录波等继等，其电力监控系统安全分区详见表1  \n表1草台第一分散式风电场电力监控系统安全分区表  \n| 序号 | 业务应用或设备 | 安全一区 | 安全二区 | 安全三区 | 互联网大区 |\n|---|---|---|---|---|---|\n| 1 | 场站监控系统 | 场站监控系统 |  |  | C |\n| 2 | 继电保护装置 | 继电保护 | 故障录波装置 |  | 0 5 |\n| 3 | 五防系统 | 五防系统 |  |  | 02 |\n| 4 | 网络安全监测 | 网络安全监测装置 | 网络安全监测装置 | 调 | 2 |\n| 5 | 电能量采集 |  | 电能量采集装置 |  |  |\n| 6 | 风功率预测系统 |  | 风功率预测系统 |  |  |\n| 7 | 有功、无功 | AGC/AVC系统 |  |  |  |\n| 8 | 天气预报系统 |  |  | 气象下载业务 | 肉李 |\n| 9 | 厂网交互系统 |  |  |  | 厂网交互系统 |\n| 10 | 就地防护终端 | 就地防护终端微型纵密 |  |  |  |\n| 11 | 安全自动控制系统 | 防孤岛保护装置 |  |  |  |\n| 12 | 测控装置 | 测控装置 |  |  |  |\n| 13 | 远动装置 | 远动装置 | 05-21 |  |  |\n| 14 | 入侵检测装置 | 入侵检测装置 |  |  |  |\n| 15 | 保信子站 | 20- | 保信子站 |  |  |\n| 16 | 故障录波 |  | 故障录波 |  |  |\n| 17 | 安全日志审 计 | 安全日志审计 |  |  |  |\n| 18 | 安全U盘隔离装置 |  | 安全U盘隔离装置 |  |  |\n| 19 | 恶意代码 |  | 恶意代码 |  |  |\n| 20 | 新 能源智 慧管控平台 | 采集服务器 |  |  | 数 据中 转服务器 |",
#                 "doc_id": "doc_4"
#             },
#             {
#                 "title": "4.2.网络专用",
#                 "text": "# 4.2.网络专用  \n草台第一分散式风电场部署两套独立配置的电力调度数据网接入设备，采用基于SDH/PDH不同通道的专用通道，第一套调度数据网设备接入中卫市地调第二套调度数据网、第二套调度数据网设备接入中卫市地调第一套调度数据网，实现物理层面上的网络专用。每一套电力调度数据网划分为逻辑隔离的实时子网与非实时子网，分别接入场站监控系统、实时/非实时网络安全监测、继电保护装置、AGC/AVC控制系统等业务。  \n电力调度数据网实时子网接入草台第一分散式风电场Ⅰ区中的场站监控系统、继电保护装置、AGC/AVC控制系统、实时网络安全监测等业务。 区调-20 区调-2  \n电力调度数据网非实时子网接入草台第一分散式风电场ⅡI区中功率预测系统、电能量采集系统、非实时网络安全监测等业务涛 李涛",
#                 "doc_id": "doc_5"
#             },
#             {
#                 "title": "4.3.橫向隔离",
#                 "text": "# 4.3.橫向隔离  \n草台第一分散式风电场部署防火墙6台，在I区和Ⅱ区之间部署防火墙1台，用于保护信息子站与站控层业务的逻辑隔离；在功率预测系统部署防火墙2台，其中功率预测内网防火墙用于功率预测系统服务器与I区远动装置的逻辑隔离，气象外网防火墙用于外网与安全III区气象服务器的逻辑隔离；在风机监控系统与监控后台部署防火墙1台，用于风机监控系统与监控后台之间业务传输的逻辑隔离；新能源智慧管理平台防火墙2台，其中智慧管控采集防火墙用于智慧管控平台安全I区采集服务器至安全一区的逻辑隔离，场站侧VPN防火墙用于互联网大区VPN专线与互联网大区转发服务器的逻辑隔离。  \n为确保功率预测系统与气象服务系统之间的数据安全，草台第一分散式风电场部署隔离装置2台，反向隔离装置1台，用于控制电站功率预测系统与安全III区气象服务器数据采集与上传的物",
#                 "doc_id": "doc_6"
#             }
#         ]
#     }
#
#     # 模拟3条规则，MAX_LLM_CONCURRENT=2，同一时刻最多2个LLM调用，第3个排队
#     test_rules = [
#         AuditRule(
#             id="R001",
#             name="法律法规判断",
#             description="法律法规判断",
#             chapter_keywords=["总则"],
#             judge_logic="判断引用的法规是否正确"
#         ),
#         AuditRule(
#             id="R001",
#             name="厂站情况判断",
#             description="厂站情况判断",
#             chapter_keywords=["系统概况"],
#             judge_logic="厂站情况描述是否齐全，是否详细"
#         ),
#         # AuditRule(
#         #     id="R001",
#         #     name="安全分区判断",
#         #     description="安全分区判断",
#         #     chapter_keywords=["安全分区"],
#         #     judge_logic="安全分区是否合理"
#         # )
#     ]
#     #
#     # input_state = {
#     #     "contract_markdown_json": contract_json,
#     #     "rule_list": test_rules,
#     #     "single_rule_results": [],
#     #     "final_report": ""
#     # }
#     # res = graph.invoke(input_state)
#     # print(res["rule_list"])
#     # print(res["single_rule_results"])
#     # print(res["final_report"])
