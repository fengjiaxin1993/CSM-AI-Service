from string import Template
from typing import Dict

from csm_ai_service.server.csm_analyze.warning_analysis.extract_info.helper import output_standard_dict
from csm_ai_service.server.utils import get_ChatOpenAI, get_default_llm, fix_llm_json_output
from csm_ai_service.settings import Settings
from csm_ai_service.utils import build_logger
logger = build_logger()

### 告警处置报告研判


# 高危研判提示词模板
high_risk_judge_prompt_template = Template("""
你是电力网络安全告警处置研判专家。本次为【高危告警】（包含但不限于 445 端口、违规外联、3389 端口、病毒、互联网地址访问等）。
工作分为两步：
1.事件研判：研判告警真实性、风险等级、事件影响；
2.报告审核：严格落实四不放过原则：事故原因是否查清、责任人员是否处理、整改措施是否落实并附佐证、有关人员是否受到教育。
结合研判规则、历史同类告警处置案例，完成本次报告研判审核。

【研判规则】
${rules_info}

【历史相似告警处置报告参考】
${retrieved_info}

【本次待审核报告】
${report_info}

## 输出强制约束

1. 仅输出纯 JSON，禁止任何额外文字、注释、说明。
2. `audit_result` 仅允许取值：`通过` / `驳回` / `需人工复核`。
3. `audit_details`：研判及审核工作记录，写明告警研判结论（告警是否属实、风险影响）、参考依据、报告整体合规概览；只做概览描述，**不罗列明细问题**，120‑150 字。
4. `conclusion`：审核综合结论：
   - 结果为`通过`：输出本次告警处置报告审核通过的总结评述；
   - 结果为`驳回`：输出面向填报人的汇总驳回修改意见；
   - 结果为`需人工复核`：输出人工复核提示与关注点；
5. `problem_list`：问题明细数组，报告缺陷、研判疑点全部收敛在此；每条内部三要素严格一一对应：
   - `text`：摘抄报告存在问题的原始文本片段；
   - `cause`：研判 / 审核视角下不合理、缺失、不合规的具体原因；
   - `suggest`：针对本条内容的整改、补全、修改建议；
   无问题时为空数组，其它字段不再重复明细问题。
   
## JSON 固定输出模板

{
    "audit_result": "",
    "audit_details": "",
    "conclusion": "",
    "problem_list": [
        {
            "text": "报告问题原文片段",
            "cause": "不合理/缺失/不合规原因",
            "suggest": "本条对应整改补全建议"
        }
    ]
}
""")

# 普通风险研判提示词模板
normal_risk_judge_prompt_template = Template("""
你是电力行业告警处置报告审核专家，本次告警为【普通告警】，审查标准适度简化，重点关注内容完整性和逻辑一致性即可；
结合研判规则、历史同类告警处置案例，完成本次报告研判审核。

【研判规则】
${rules_info}

【历史相似告警处置报告参考】
${retrieved_info}

【本次待审核报告】
${report_info}

## 输出强制约束

1. 仅输出纯 JSON，禁止任何额外文字、注释、说明。
2. `audit_result` 仅允许取值：`通过` / `驳回` / `需人工复核`。
3. `audit_details`：研判及审核工作记录，写明告警研判结论（告警是否属实、风险影响）、参考依据、报告整体合规概览；只做概览描述，**不罗列明细问题**，120‑150 字。
4. `conclusion`：审核综合结论：
   - 结果为`通过`：输出本次告警处置报告审核通过的总结评述；
   - 结果为`驳回`：输出面向填报人的汇总驳回修改意见；
   - 结果为`需人工复核`：输出人工复核提示与关注点；
5. `problem_list`：问题明细数组，报告缺陷、研判疑点全部收敛在此；每条内部三要素严格一一对应：
   - `text`：摘抄报告存在问题的原始文本片段；
   - `cause`：研判 / 审核视角下不合理、缺失、不合规的具体原因；
   - `suggest`：针对本条内容的整改、补全、修改建议；
   无问题时为空数组，其它字段不再重复明细问题。

## JSON 固定输出模板

{
    "audit_result": "",
    "audit_details": "",
    "conclusion": "",
    "problem_list": [
        {
            "text": "报告问题原文片段",
            "cause": "不合理/缺失/不合规原因",
            "suggest": "本条对应整改补全建议"
        }
    ]
}
""")



def init_analyze_result_json_data() -> Dict:
    """初始化研判结论结构化字段（中文键）"""
    return {
        "audit_result": "需人工复核",
        "audit_details": "",
        "conclusion": "",
        "problem_list": [
            {
                "text": "",
                "cause": "",
                "suggest": ""
            }
        ]
    }

def build_report_judge_prompt(is_high_risk:bool, rules_info: str,retrieved_info: str, report_info:str ) -> str:
    if is_high_risk:
        return high_risk_judge_prompt_template.substitute(rules_info=rules_info,retrieved_info=retrieved_info,report_info=report_info)
    else:
        return normal_risk_judge_prompt_template.substitute(rules_info=rules_info,retrieved_info=retrieved_info,report_info=report_info)



# 通过llm进行告警研判
def judge_report_by_llm(is_high_risk:bool, rules_info: str,retrieved_info: str, report_info:str) -> Dict:

    model = get_default_llm()
    llm = get_ChatOpenAI(
        model_name=model,
        temperature=0.1,
        max_tokens=Settings.model_settings.MAX_TOKENS * 4,
    )

    # 构建提示词
    prompt = build_report_judge_prompt(is_high_risk, rules_info, retrieved_info, report_info)
    response = llm.invoke(prompt)  # 一次性调用模型，返回完整响应
    content = str(response.content)  # 核心：提取完整回答文本
    fix_dic = fix_llm_json_output(content)
    return output_standard_dict(init_analyze_result_json_data(), fix_dic)
