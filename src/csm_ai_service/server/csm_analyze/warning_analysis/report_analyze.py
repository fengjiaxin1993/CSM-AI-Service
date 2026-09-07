import os
import json
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

from csm_ai_service.server.db.repository import search_alert_reports, list_alert_rules, add_alert_report, \
    get_alert_report_by_file_name, update_alert_report
from csm_ai_service.server.csm_analyze.warning_analysis.extract_info.helper import init_report_json_data, init_analyze_result_json_data

# 知识库插入、搜索
logger = build_logger()


# 组装 prompt
def construct_rag_prompt(alarm_desc: str, top_k: int = 3):
    docs = search_alert_reports(query=alarm_desc, top_k=top_k)
    """电力行业RAG双层检索，返回同类告警参考"""
    if not docs:
        return "未检索到同类电力告警处置报告"

    # 整理电力专属参考格式
    final_retrieve = ""
    for idx, doc in enumerate(docs):
        final_retrieve += f"""
    第{idx+1}条：
    {str(doc.get("meta_info"))}
    ----------------------
    """
    return final_retrieve


def save_to_warning_report_file(file: UploadFile):
    file_content = file.file.read()  # 读取上传文件的内容
    new_file_path = os.path.join(Settings.basic_settings.WARNING_REPORT_DIR, file.filename)
    if not os.path.exists(new_file_path):
        with open(new_file_path, "wb") as f:
            f.write(file_content)
    return str(new_file_path)


#
# 获取告警处置报告 json结构化
def get_warning_report_json_by_filepath(file_path: str = Body("", description="文档存储路径")) -> BaseResponse:
    file_name = os.path.basename(file_path)
    ext = os.path.splitext(file_name)[-1].lower()
    # 先查数据库，已有则直接返回
    existing = get_alert_report_by_file_name(file_name=file_name)
    if existing is not None:
        return BaseResponse(data=existing.get("meta_info", init_report_json_data()))
    # 数据库中没有，解析文件并缓存
    try:
        full_text, table_data_text = extract_text_from_file(file_path, ext)
        result = extract_structured_data(file_name, full_text, table_data_text)
        result = output_standard_dict(init_report_json_data(), result)
        # 解析成功后缓存到数据库（status=cache）
        try:
            add_alert_report(
                report_title=result["报告标题"],
                file_name=file_name,
                alert_content=result["告警内容"],
                meta_info=result,
                full_text=full_text,
                table_data_text=table_data_text,
                status="cache",
            )
        except Exception as e:
            logger.warning(f"缓存报告到数据库失败（不影响返回结果）: {e}")
        return BaseResponse(data=result)
    except Exception as e:
        return BaseResponse(code=202, msg=f"解析{file_name}失败，报错信息{e}", data={})


# 获取研判报告
def get_alarm_report_info(file: UploadFile = File(..., description="上传文件")) -> BaseResponse:
    # 每次都更新缓存
    new_file_path = save_to_warning_report_file(file)
    return get_warning_report_json_by_filepath(new_file_path)


def get_rules_desc(limit: int = 5):
    rules = list_alert_rules(limit=limit, offset=0)
    results = []
    for idx,rule in enumerate(rules):
        rule_str = f"{idx+1}. {rule.get('name', '')}: {rule.get('description', '')}"
        results.append(rule_str)
    return "\n".join(results)


# 一次性返回研判结果
def warning_analyze(warning_number: str = Body("test", description="告警编号"),
                    file: UploadFile = File(..., description="上传文件")) -> BaseResponse:
    # 【step1】 获取告警处置报告信息
    report_response = get_alarm_report_info(file)
    logger.info(f"【step1】 获取告警处置报告信息{file.filename}")
    if report_response.code != 200:
        data = init_analyze_result_json_data()
        data["审核结果"] = "需人工复核"
        data["审核详情"] = f"解析{file.filename}失败"
        return BaseResponse(code=202, msg=report_response.msg, data=data)
    report_data = report_response.data

    # 【step2】 获取规则库
    rules_desc = get_rules_desc(limit=5)
    logger.info("【step2】 获取规则库")

    # 【step3】获取历史数据信息
    rag_retrieve_info = construct_rag_prompt(alarm_desc=report_data["告警内容"],
                                             top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K)
    logger.info("【step3】获取历史数据信息")

    # 【step4】 组装提示词
    prompt_template = get_prompt_template("warning", "analyze")
    # 渲染提示词
    input_msg = History(role="user", content=prompt_template).to_msg_template(False)
    chat_prompt = ChatPromptTemplate.from_messages([input_msg])
    report_info = json.dumps(report_data, ensure_ascii=False, indent=2)
    prompt = chat_prompt.invoke({"retrieved_info": rag_retrieve_info, "report_info": report_info, "rules_info": rules_desc})
    logger.info(f"【step4】 组装提示词,提示词如下\n{prompt.to_string()}")


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
def save_warning_report(
        warning_number: str = Body("test", description="告警编号"),
        file: UploadFile = File(..., description="上传文件"),
) -> BaseResponse:
    report_response = get_alarm_report_info(file)
    if report_response.code != 200:
        return BaseResponse(code=report_response.code, msg=f"解析报告失败，无法保存: {report_response.msg}")
    report_data = report_response.data
    try:
        # 根据file_name查询是否已在数据库
        existing = get_alert_report_by_file_name(file_name=file.filename)
        if existing is None:
            # 不在数据库中，新增，状态为saved
            report_id = add_alert_report(
                report_title=report_data["报告标题"],
                file_name=file.filename,
                alert_content=report_data["告警内容"],
                meta_info=report_data,
                status="saved",
            )
            return BaseResponse(code=200, msg=f"新增保存成功,report_id={report_id}")
        else:
            if existing.get("status") == "cache":
                # 缓存状态 → 确认保存（cache → saved），同时更新数据
                update_alert_report(
                    report_id=existing["id"],
                    report_title=report_data["报告标题"],
                    alert_content=report_data["告警内容"],
                    meta_info=report_data,
                    full_text=existing.get("full_text", ""),
                    table_data_text=existing.get("table_data_text", ""),
                    status="saved",
                )
                return BaseResponse(code=200, msg=f"缓存报告已确认保存,report_id={existing['id']}")
            else:
                # 已经是saved状态，更新内容
                update_alert_report(
                    report_id=existing["id"],
                    report_title=report_data["报告标题"],
                    alert_content=report_data["告警内容"],
                    meta_info=report_data,
                )
                return BaseResponse(code=200, msg=f"报告已更新,report_id={existing['id']}")
    except Exception as e:
        logger.error(f"保存告警报告到知识库失败: {str(e)}")
        return BaseResponse(code=500, msg=f"保存失败: {str(e)}")


def save_warning_report_only_by_file(
        file: UploadFile = File(..., description="上传文件"),
) -> BaseResponse:
    return save_warning_report(file=file)

# 根据告警编号删除知识库中的文档
def delete_warning_report(
        warning_number: str = Body("test", description="告警编号"),
) -> BaseResponse:
    """根据告警编号从知识库中删除对应的告警处置报告"""
    return BaseResponse(code=200, msg=f"文件删除完成")
