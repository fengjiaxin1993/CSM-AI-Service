import hashlib
import json
import os
from typing import List, Optional
from json_repair import repair_json
from fastapi import Body, UploadFile, File
from langchain_core.prompts import ChatPromptTemplate
from server.chat.utils import History
from server.utils import get_default_llm, get_ChatOpenAI, get_prompt_template, BaseResponse
from server.warning_analysis.chromadb_kb_service import ChromaKBService, DDoc
from server.warning_analysis.extract_pdf_info import PowerAlarmReportParser
from settings import Settings
from server.utils import build_logger

# 知识库插入、搜索
logger = build_logger()


# 从告警库中搜索相关告警信息
def search_alarm(alarm_desc: str) -> List[tuple[DDoc, float]]:
    kb_service = ChromaKBService(Settings.kb_settings.WARNING_KNOWLEDGE)
    doc_list = kb_service.query(query=alarm_desc,
                                top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K,
                                score_threshold=Settings.kb_settings.SCORE_THRESHOLD)
    return doc_list


# 组装 prompt
def rag_retrieve(alarm_desc: str):
    ddoc_list = search_alarm(alarm_desc)
    """电力行业RAG双层检索，返回同类告警参考"""
    if not ddoc_list:
        return "未检索到同类电力告警处置报告"

    # 整理电力专属参考格式
    final_retrieve = "【同类电力告警处置参考】\n"
    for idx, ddoc, sim in enumerate(ddoc_list):
        final_retrieve += f"""
    第{idx}条（相似度：{sim}）：
    
    告警信息描述：{ddoc.doc} 设备名称：{ddoc.meta["设备名称"]} 设备类型：{ddoc.meta["设备类型"]}
    处置过程：{ddoc.meta["处置过程"]}
    原因分析：{ddoc.meta["原因分析"]}
    整改情况：{ddoc.meta["整改情况"]}
    防范措施：{ddoc.meta["防范措施"]}
    ----------------------
    """
    return final_retrieve


def compute_str_md5(name: str) -> str:
    md5 = hashlib.md5()
    md5.update(name.encode('utf-8'))
    return md5.hexdigest()


# 保存，返回临时路径
def save_to_temp_file(file: UploadFile):
    file_content = file.file.read()  # 读取上传文件的内容
    # prefix, suffix = os.path.splitext(file.filename)
    # new_file_prefix = compute_str_md5(prefix)
    # new_file_name = new_file_prefix + "." + suffix
    new_file_path = os.path.join(Settings.basic_settings.BASE_TEMP_DIR, file.filename)
    with open(new_file_path, "wb") as f:
        f.write(file_content)
    return str(new_file_path)


# 修复大模型输出库
def fix_llm_json_output(bad_json_str: str) -> dict:
    try:
        # 第一步：尝试直接解析（如果本身没问题，直接返回）
        return json.loads(bad_json_str)
    except json.JSONDecodeError:
        pass

    try:
        # 核心修复逻辑：repair_json会自动处理引号、逗号、括号等常见错误
        repaired_json_str = repair_json(
            bad_json_str,
            # 可选配置：根据需求调整
            ensure_ascii=False,  # 保留中文等非ASCII字符
            return_objects=True  # 确保修复后是JSON对象（而非数组/字符串）
        )
        return json.loads(repaired_json_str)
    except Exception as e:
        logger.error(f"使用json_repair解析{bad_json_str}结果失败: {str(e)}")
        return {}


#
def init_warning_fields() -> dict:
    """初始化告警研判结果"""
    return {
        "audit_result": "需人工复核",  # 通过/驳回/需人工复核
        "audit_details": "",  # 分维度说明审核结果
        "summary": "",  # 报告核心总结（100字内，含告警类型、处置结果、合规情况）
        "reject_reason": "",  # 驳回需说明具体修改要求，否则为空
        "power_suggestion": "",  # 电力行业专属优化建议
    }


# 根据标准答案，从llm输出的结果进行校验
def normalize_warning_output(content: str) -> dict:
    fix_dic = fix_llm_json_output(content)
    res_dic = init_warning_fields()
    for k in res_dic.keys():
        if k in fix_dic.keys():
            res_dic[k] = fix_dic[k]
    return res_dic


# 校验告警处置报告是否缺失字段
def check_report(dic) -> tuple[bool, list]:
    keys = ["报告标题", "告警信息", "设备名称", "设备类型", "告警时间",
            "告警内容", "处置过程", "原因分析", "整改情况", "防范措施"]
    empty_list = []
    for key in keys:
        if not dic[key]:  # 为空
            empty_list.append(key)
    return len(empty_list) == 0, empty_list


# 一次性返回研判结果
def warning_analyze(file: UploadFile = File(..., description="上传文件"),
                    model: str = Body(get_default_llm(), description="LLM 模型名称。"),
                    max_tokens: Optional[int] = Body(
                        Settings.model_settings.MAX_TOKENS,
                        description="限制LLM生成Token数量，默认None代表模型最大值"
                    )) -> BaseResponse:
    new_file_path = save_to_temp_file(file)
    try:
        parser = PowerAlarmReportParser(new_file_path)
        result = parser.parse()
    except Exception as e:
        return BaseResponse(code=202, msg=f"解析{file.filename}失败，报错信息{e}")

    flag, empty_list = check_report(result)
    if not flag:
        empty_str = ",".join(empty_list)
        return BaseResponse(code=204, msg=f"处置报告{file.filename}缺失关键信息，缺失字段有{empty_str}")

    rag_retrieve_info = rag_retrieve(alarm_desc=result["告警信息"])
    report_info = json.dumps(result, ensure_ascii=False, indent=2)
    llm = get_ChatOpenAI(
        model_name=model,
        temperature=0.1,
        max_tokens=max_tokens,
    )

    prompt_template = get_prompt_template("warning", "default")
    # 渲染提示词
    input_msg = History(role="user", content=prompt_template).to_msg_template(False)
    chat_prompt = ChatPromptTemplate.from_messages([input_msg])
    prompt = chat_prompt.invoke({"retrieved_info": rag_retrieve_info, "report_info": report_info})
    print(prompt.to_string())
    response = llm.invoke(prompt)  # 一次性调用模型，返回完整响应

    content = response.content  # 核心：提取完整回答文本
    print(content)
    res_dic = normalize_warning_output(content)
    print(res_dic)
    return BaseResponse(data=res_dic)
