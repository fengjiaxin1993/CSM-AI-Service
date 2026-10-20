import os
import json
from typing import Dict

from fastapi import Body, UploadFile, File
from langchain_core.prompts import ChatPromptTemplate
from csm_ai_service.server.utils import get_default_llm, get_ChatOpenAI, get_prompt_template, BaseResponse, \
    fix_llm_json_output

from csm_ai_service.server.conversation.chat.utils import History
from csm_ai_service.server.csm_analyze.warning_analysis.extract_info.helper import output_standard_dict
from csm_ai_service.server.csm_analyze.warning_analysis.extract_structed_data import extract_text_from_file, \
    extract_structured_data
from csm_ai_service.settings import Settings
from csm_ai_service.utils import build_logger

##### 兼容之前的api接口
logger = build_logger()


# 高危告警判断 prompt
_HIGH_RISK_JUDGE_PROMPT = """你是电力监控系统告警分级专家。请根据以下告警内容，判断该告警是否属于高危告警。

高危告警的特征包括但不限于：
1. 445端口相关告警（如端口扫描、端口爆破、SMB漏洞利用等）
2. 违规外联/非法外联（内网设备未经授权连接外部网络）
3. 3389端口相关告警（如远程桌面暴力破解、RDP漏洞利用等）
4. 病毒/木马/恶意程序/恶意代码/勒索/挖矿/后门等恶意软件告警
5. 互联网地址访问（内网设备访问互联网地址）
6. 其他严重威胁电力监控系统安全的告警

普通告警的特征：
- 一般性的端口告警（非445/3389等高危端口）
- 常规的设备状态告警
- 低风险的网络行为告警
- 不涉及安全威胁的运维类告警

【告警内容】
{alert_content}

请严格按以下JSON格式输出，不要输出其他任何内容：
{{"is_high_risk": true或false, "reason": "简要说明判断理由"}}"""


def is_high_risk_alert(alert_content: str) -> bool:
    """通过大模型判断告警是否为高危告警，返回True/False"""
    if not alert_content:
        return False
    try:
        llm = get_ChatOpenAI(
            model_name=get_default_llm(),
            temperature=0,
            max_tokens=200,
        )
        prompt = _HIGH_RISK_JUDGE_PROMPT.format(alert_content=alert_content[:2000])
        response = llm.invoke(prompt)
        result = fix_llm_json_output(response.content)
        is_high = result.get("is_high_risk", False)
        reason = result.get("reason", "")
        logger.info(f"大模型判断高危告警结果：is_high_risk={is_high}，理由：{reason}")
        return bool(is_high)
    except Exception as e:
        logger.warning(f"大模型判断高危告警失败，降级为普通告警: {e}")
        return False



def init_analyze_result_json_data() -> Dict:
    """初始化研判结论结构化字段（中文键）"""
    return {
        "audit_result": "需人工复核",
        "audit_details": "",
        "summary": "",
        "reject_reason": "",
        "power_suggestion": ""
    }


def init_report_json_data() -> Dict:
    """初始化报告结构化字段（中文键）"""
    return {
        "报告标题": "",
        "告警信息": "",
        "设备名称": "",
        "设备类型": "",
        "告警时间": "",
        "告警内容": "",
        "处置过程": "",
        "原因分析": "",
        "责任人员和责任单位处理": "",
        "人员教育培训": "",
        "整改情况": "",
        "佐证材料": "",
    }

# 组装 prompt
def construct_rag_prompt(alarm_desc: str, top_k: int = 3):
    return "未检索到同类电力告警处置报告"


def save_to_warning_report_file(file: UploadFile):
    file_content = file.file.read()  # 读取上传文件的内容
    new_file_path = os.path.join(Settings.basic_settings.WARNING_REPORT_DIR, file.filename)
    if not os.path.exists(new_file_path):
        with open(new_file_path, "wb") as f:
            f.write(file_content)
    return str(new_file_path)


# 获取告警处置报告 json结构化
def get_warning_report_json_by_filepath(file_path: str = Body("", description="文档存储路径")) -> BaseResponse:
    file_name = os.path.basename(file_path)
    ext = os.path.splitext(file_name)[-1].lower()
    try:
        full_text, table_data_text = extract_text_from_file(file_path, ext)
        result = extract_structured_data(file_name, full_text, table_data_text)
        result = output_standard_dict(init_report_json_data(), result)
        # 解析成功后缓存到数据库（status=cache）
        return BaseResponse(data=result)
    except Exception as e:
        return BaseResponse(code=202, msg=f"解析{file_name}失败，报错信息{e}", data={})


# 获取研判报告
def get_alarm_report_info(file: UploadFile = File(..., description="上传文件")) -> BaseResponse:
    # 每次都更新缓存
    new_file_path = save_to_warning_report_file(file)
    return get_warning_report_json_by_filepath(new_file_path)

DEFAULT_ALERT_RULES = [
    {
        "rule_code": "RULE_001",
        "name": "内容完整性检查",
        "description": "内容要完整，包括原因分析、整改结果、佐证材料等内容，关键信息无缺失。如设备的型号、故障排查过程，是否举一反三进行了全面排查和整改等。",
    },
    {
        "rule_code": "RULE_002",
        "name": "逻辑一致性检查",
        "description": "由大模型对报告全文进行阅读，分析有没有逻辑不通的内容，比如前后不一致、原因分析与处置措施没有关联关系等等，结合知识库判断内容有没有错误的地方。",
    },
    {
        "rule_code": "RULE_003",
        "name": "四不放过原则检查",
        "description": "针对有威胁的告警，目前就是违规外联这一种类型的告警，要按照四不放过原则去审视告警分析报告，事故原因有没有查清楚、有没有对责任人员的处理结果、报告中的整改措施有没有落实的佐证、有关人员有没有受到教育比如有没有培训记录等等。读分析报告有没有做到这四个方面。",
    },
]

def get_rules_desc(limit: int = 5):
    results = []
    for idx,rule in enumerate(DEFAULT_ALERT_RULES):
        rule_str = f"{idx+1}. {rule.get('name', '')}: {rule.get('description', '')}"
        results.append(rule_str)
    return "\n".join(results)


# 一次性返回研判结果
def warning_report_analyze(warning_number: str = Body("test", description="告警编号"),
                    file: UploadFile = File(..., description="上传文件")) -> BaseResponse:
    # 【step1】 获取告警处置报告信息
    report_response = get_alarm_report_info(file)
    logger.info(f"【step1】 获取告警处置报告信息{file.filename}")
    if report_response.code != 200:
        data = init_analyze_result_json_data()
        data["audit_result"] = "需人工复核"
        data["audit_details"] = f"解析{file.filename}失败"
        return BaseResponse(code=202, msg=report_response.msg, data=data)
    report_data = report_response.data

    # 【step2】 判断是否为高危告警
    alert_content = report_data.get("告警内容", "")
    is_high_risk = is_high_risk_alert(alert_content)
    risk_level = "高危告警" if is_high_risk else "普通告警"
    logger.info(f"【step2】 告警类型判定：{risk_level}，告警内容片段：{alert_content[:100]}")

    # 【step3】 获取规则库
    rules_desc = get_rules_desc(limit=5)
    logger.info("【step2】 获取规则库")

    # 【step4】获取历史数据信息
    rag_retrieve_info = construct_rag_prompt(alarm_desc=report_data["告警内容"],
                                             top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K)
    logger.info("【step3】获取历史数据信息")

    # 【step5】 组装提示词（根据高危/普通选择不同模板）
    prompt_name = "analyze_high_risk" if is_high_risk else "analyze_normal"
    prompt_template = get_prompt_template("warning", prompt_name)
    # 渲染提示词
    input_msg = History(role="user", content=prompt_template).to_msg_template(False)
    chat_prompt = ChatPromptTemplate.from_messages([input_msg])
    report_info = json.dumps(report_data, ensure_ascii=False, indent=2)
    prompt = chat_prompt.invoke({"retrieved_info": rag_retrieve_info, "report_info": report_info, "rules_info": rules_desc})
    logger.info(f"【step4】 组装提示词（{risk_level}，模板={prompt_name}），提示词如下\n{prompt.to_string()}")


    # 【step5】 调用大模型
    llm = get_ChatOpenAI(
        model_name=get_default_llm(),
        temperature=0.1,
        max_tokens=Settings.model_settings.MAX_TOKENS,
    )
    try:
        response = llm.invoke(prompt)  # 一次性调用模型，返回完整响应
        content = response.content  # 核心：提取完整回答文本
        logger.info(f"\n【step 5】大模型研判原始文本: \n{content}")
        res_dic = fix_llm_json_output(content)
        logger.info(f"\n【step 5】修复智能研判结果json: \n{res_dic}")
        res_dic = output_standard_dict(init_analyze_result_json_data(), res_dic)
        return BaseResponse(data=res_dic)
    except Exception as e:
        data = init_analyze_result_json_data()
        data["audit_result"] = "需人工复核"
        return BaseResponse(code=203, msg=f"大模型分析{file.filename}失败，请人工查看，报错信息{e}", data=data)


# 保存处置报告
def mock_save_warning_report(
        warning_number: str = Body("test", description="告警编号"),
        file: UploadFile = File(..., description="上传文件"),
) -> BaseResponse:
    return BaseResponse(code=200, msg=f"保存成功")

# 根据告警编号删除知识库中的文档
def mock_delete_warning_report(
        warning_number: str = Body("test", description="告警编号"),
) -> BaseResponse:
    """根据告警编号从知识库中删除对应的告警处置报告"""
    return BaseResponse(code=200, msg=f"文件删除完成")
