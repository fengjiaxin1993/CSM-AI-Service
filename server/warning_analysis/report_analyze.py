import hashlib
import json
import os
from typing import List, Optional, Tuple
from json_repair import repair_json
from fastapi import Body, UploadFile, File
from langchain_core.prompts import ChatPromptTemplate
from server.chat.utils import History
from server.utils import get_default_llm, get_ChatOpenAI, get_prompt_template, BaseResponse, get_default_embedding
from langchain.docstore.document import Document

from server.warning_analysis.extract_info.pdfAlarmReportParser import PDFAlarmReportParser
# from server.warning_analysis.extract_info.scanPdfAlarmReportParser import ScannedPdfReportParser
from server.warning_analysis.extract_info.wordAlarmReportParser import WORDAlarmReportParser
from server.knowledge_base.kb_service.base import KBServiceFactory
from settings import Settings
from utils import build_logger
from server.knowledge_base.utils import (
    KnowledgeFile,
    get_file_path,
)

# 知识库插入、搜索
logger = build_logger()


def _get_or_create_warning_kb():
    """获取或创建告警知识库服务实例"""
    kb_name = Settings.kb_settings.WARNING_KNOWLEDGE
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        # 知识库不存在，自动创建
        logger.info(f"告警知识库 {kb_name} 不存在，正在自动创建...")
        kb = KBServiceFactory.get_service(
            kb_name=kb_name,
            vector_store_type=Settings.kb_settings.DEFAULT_VS_TYPE,
            embed_model=get_default_embedding(),
            kb_info="电力行业告警处置报告知识库"
        )
        try:
            kb.create_kb()
            logger.info(f"告警知识库 {kb_name} 创建成功")
        except Exception as e:
            logger.error(f"创建告警知识库失败: {str(e)}")
            return None
    return kb


# 从告警库中搜索相关告警信息
def search_alarm(alarm_desc: str,
                 top_k: int,
                 score_threshold: float) -> List[Tuple[Document, float]]:
    kb = _get_or_create_warning_kb()
    if kb is None:
        logger.warning("告警知识库不存在，请先创建")
        return []
    # 执行查询
    docs_with_scores = kb.search_docs(
        query=alarm_desc,
        top_k=top_k,
        score_threshold=score_threshold
    )
    return docs_with_scores


# 组装 prompt
def construct_rag_prompt(alarm_desc: str, top_k: int, score_threshold: float):
    docs_with_scores = search_alarm(alarm_desc, top_k, score_threshold)
    """电力行业RAG双层检索，返回同类告警参考"""
    if not docs_with_scores:
        return "未检索到同类电力告警处置报告"

    # 整理电力专属参考格式
    final_retrieve = "【同类电力告警处置参考】\n"
    for idx, (ddoc, sim) in enumerate(docs_with_scores):
        final_retrieve += f"""
    第{idx}条（相似度：{sim}）：
    
    告警信息描述：{ddoc.page_content} 设备名称：{ddoc.metadata.get("设备名称", "")} 设备类型：{ddoc.metadata.get("设备类型", "")}
    处置过程：{ddoc.metadata.get("处置过程", "")}
    原因分析：{ddoc.metadata.get("原因分析", "")}
    整改情况：{ddoc.metadata.get("整改情况", "")}
    防范措施：{ddoc.metadata.get("防范措施", "")}
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
    if os.path.exists(new_file_path):
        os.remove(new_file_path)
    with open(new_file_path, "wb") as f:
        f.write(file_content)
    return str(new_file_path)


def save_to_target_file(file: UploadFile, target_file_path):
    file_content = file.file.read()  # 读取上传文件的内容
    if os.path.exists(target_file_path):
        os.remove(target_file_path)
    with open(target_file_path, "wb") as f:
        f.write(file_content)
    return str(target_file_path)


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


def extract_dic_from_file(file_path: str, ext: str):
    result = {}
    if ext == ".docx":
        parser = WORDAlarmReportParser(file_path)
        result = parser.parse()
    elif ext == ".pdf":
        parser = PDFAlarmReportParser(file_path)
        result = parser.parse()
        # flag, empty_list = check_report(result)
        # if not flag:  # 尝试
        #     parser = ScannedPdfReportParser(file_path)
        #     result = parser.parse()
    return result


# 一次性返回研判结果
def warning_analyze(warning_number: str = Body("test", description="告警编号"),
                    file: UploadFile = File(..., description="上传文件"),
                    model: str = Body(get_default_llm(), description="LLM 模型名称。"),
                    max_tokens: Optional[int] = Body(
                        Settings.model_settings.MAX_TOKENS,
                        description="限制LLM生成Token数量，默认None代表模型最大值"
                    ),
                    top_k: Optional[int] = Body(
                        Settings.kb_settings.VECTOR_SEARCH_TOP_K,
                        description="最多搜索top_k条相似告警"
                    ),
                    score_threshold: Optional[float] = Body(
                        Settings.kb_settings.SCORE_THRESHOLD,
                        description="相似度阈值"
                    )) -> BaseResponse:
    new_file_path = save_to_temp_file(file)
    result = None
    ext = os.path.splitext(file.filename)[-1].lower()
    try:
        result = extract_dic_from_file(new_file_path, ext)
    except Exception as e:
        return BaseResponse(code=202, msg=f"解析{file.filename}失败，报错信息{e}", data=init_warning_fields())

    flag, empty_list = check_report(result)
    if not flag:
        empty_str = ",".join(empty_list)
        return BaseResponse(code=204, msg=f"处置报告{file.filename}缺失关键信息，缺失字段有{empty_str}", data=init_warning_fields())
    try:
        rag_retrieve_info = construct_rag_prompt(alarm_desc=result["告警信息"], top_k=top_k,
                                                 score_threshold=score_threshold)
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
        # print(prompt.to_string())
        response = llm.invoke(prompt)  # 一次性调用模型，返回完整响应

        content = response.content  # 核心：提取完整回答文本
        # print(content)
        res_dic = normalize_warning_output(content)
        # print(res_dic)
        return BaseResponse(data=res_dic)
    except Exception as e:
        return BaseResponse(code=202, msg=f"解析失败，报错信息{e}", data=init_warning_fields())


# 保存处置报告
def save_warning_report(
        warning_number: str = Body("test", description="告警编号"),
        file: UploadFile = File(..., description="上传文件"),
) -> BaseResponse:
    target_file_path = get_file_path(
        knowledge_base_name=Settings.kb_settings.WARNING_KNOWLEDGE, doc_name=file.filename
    )
    save_to_target_file(file, target_file_path)
    result = {}
    ext = os.path.splitext(file.filename)[-1].lower()
    try:
        result = extract_dic_from_file(target_file_path, ext)
    except Exception as e:
        return BaseResponse(code=200, msg=f"解析{file.filename}失败，报错信息{e}，暂时不存在向量库中")

    flag, empty_list = check_report(result)
    if not flag:
        empty_str = ",".join(empty_list)
        return BaseResponse(code=200,
                            msg=f"处置报告{file.filename}缺失关键信息，缺失字段有{empty_str}，暂时不存在向量库中")

    # 获取告警知识库服务
    kb = _get_or_create_warning_kb()
    if kb is None:
        return BaseResponse(code=500, msg="告警知识库创建失败")

    # 加入告警编号信息
    result["warning_number"] = warning_number
    # 构建 Document 对象
    doc = Document(
        page_content=result["告警信息"],
        metadata=result
    )

    # 创建虚拟文件对象用于 add_doc
    kb_file = KnowledgeFile(
        filename=file.filename,
        knowledge_base_name=Settings.kb_settings.WARNING_KNOWLEDGE
    )

    # 使用 KBService 的 add_doc 方法，传入自定义 docs
    try:
        status = kb.add_doc(kb_file, docs=[doc])
        if status:
            return BaseResponse(code=200, msg="保存成功")
        else:
            return BaseResponse(code=500, msg="保存到知识库失败")
    except Exception as e:
        logger.error(f"保存告警报告到知识库失败: {str(e)}")
        return BaseResponse(code=500, msg=f"保存失败: {str(e)}")


# 根据告警编号删除知识库中的文档
def delete_warning_report(
        warning_number: str = Body("test", description="告警编号"),
) -> BaseResponse:
    """根据告警编号从知识库中删除对应的告警处置报告"""
    if not warning_number or not warning_number.strip():
        return BaseResponse(code=400, msg="告警编号不能为空")

    # 获取告警知识库服务
    kb = _get_or_create_warning_kb()
    if kb is None:
        return BaseResponse(code=404, msg="告警知识库不存在")

    # 根据告警编号检索文档
    try:
        docs = kb.list_docs(metadata={"warning_number": warning_number})
        if not docs:
            return BaseResponse(code=404, msg=f"未找到告警编号为 {warning_number} 的处置报告")
        file_names = set()
        for doc in docs:
            file_names.add(doc.metadata['source'])
        valid_file_names = []
        for file_name in file_names:
            if not kb.exist_doc(file_name):
                continue
            try:

                kb_file = KnowledgeFile(
                    filename=file_name, knowledge_base_name=Settings.kb_settings.WARNING_KNOWLEDGE
                )
                kb.delete_doc(kb_file, True, not_refresh_vs_cache=True)
                valid_file_names.append(file_name)
            except Exception as e:
                msg = f"{file_name} 文件删除失败，错误信息：{e}"
                logger.error(f"{e.__class__.__name__}: {msg}")

            kb.save_vector_store()

        return BaseResponse(
            code=200, msg=f"文件删除完成", data={"delete_files": valid_file_names}
        )

    except Exception as e:
        logger.error(f"根据告警编号删除文档失败: {str(e)}")
        return BaseResponse(code=500, msg=f"删除失败: {str(e)}")
