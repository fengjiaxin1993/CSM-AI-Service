# 识别pdf扫描件 markdown格式的服务
"""
RapidDoc 服务 - 支持并发限制为 3
提供 PDF 解析 API，返回 OCR 结果和 bbox 信息
"""
import logging
import time
import fitz  # PyMuPDF
import httpx
from fastapi import Body
from csm_ai_service.server.protection_audit.text_pdf_parser import parse_text_pdf
# 屏蔽 rapid_doc 及其相关库的日志
logging.getLogger("faiss").setLevel(logging.ERROR)

from csm_ai_service.server.protection_audit.tools.ocr_tools import handle_pdfParseResult
import os
from typing import Dict
from csm_ai_service.server.utils import build_logger
from csm_ai_service.settings import Settings

logger = build_logger()


# 扫描文件类型pdf, 通过访问服务解决吧
def scanPdf2info(
        file_path: str = Body(None, embed=True, description="文件路径")
):
    """
    只做OCR识别，不做任何前置校验

    - **file**: PDF 文件
    - **return_markdown**: 是否返回 Markdown
    """
    ocr_url = Settings.basic_settings.OCR_SERVICE_URL
    with httpx.Client(base_url=ocr_url, timeout=Settings.basic_settings.OCR_TIMEOUT) as c:
        r = c.post(
            "/api/parse/pdf2info",
            json={"file_path": file_path})

    resp = r.json()
    return resp

# 文本类型pdf提取信息
def textPdf2info(
        file_path: str = Body(None, embed=True, description="文件路径")
):
    """
    只做文本类型信息提取
    """
    file_name = os.path.basename(file_path)
    total_pages = 0
    with fitz.open(file_path) as doc:
        total_pages = doc.page_count

    logger.info(f"调用textPdf2info方法, file_name:{file_name}, 总页数:{total_pages}")
    result = {
        "success": False,
        "processing_time": 0.0,
        "markdown_text": "",
        "locate_json_result": {},
        "structure_json_result": {},
        "error": ""
    }

    start_time = time.time()
    try:
        pdfParseResult = parse_text_pdf(file_path)
        res_dic = handle_pdfParseResult(pdfParseResult)

        result["success"] = True
        result["processing_time"] = time.time() - start_time
        result["markdown_text"] = res_dic["markdown"]
        result["locate_json_result"] = res_dic["layoutParsingResults"]
        result["structure_json_result"] = res_dic["structureJsonResults"]
        logger.info(
            f"pdf2info处理完成，文件: {file_name}, "
            f"页数: {total_pages}, 耗时: {result['processing_time']:.2f}秒"
        )
        return result

    except Exception as e:
        logger.error(f"处理文件失败: {e}")
        result["error"] = str(e)
        return result





def process_file_ocr_by_path(file_path: str) -> Dict:
    """
    解析 PDF 文件，先尝试文本PDF解析，若文字不足且开启了OCR则进一步调用OCR服务。
    用于 task_queue 异步任务流程

    Args:
        file_path: 文件路径

    Returns:
        {
            "locate_json_result": dict,
            "markdown_text": str,
            "structure_json_result": dict
        }
    """
    if not os.path.exists(file_path):
        return {'error': f"文件不存在: {file_path}"}

    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext != '.pdf':
        return {'error': f"不支持该文件格式: {file_path}"}

    try:
        # 第一步：始终先执行文本PDF解析
        logger.info(f"开始文本PDF解析: {file_path}")
        text_result = textPdf2info(file_path)

        if not text_result.get("success", False):
            logger.warning(f"文本PDF解析失败: {text_result.get('error', '未知错误')}")

        # 判断文本解析结果中的文字数量
        markdown_text = text_result.get("markdown_text", "")
        text_length = len(markdown_text.strip())

        # 获取配置
        ocr_enabled = Settings.basic_settings.OCR_ENABLED
        min_text_length = Settings.basic_settings.OCR_MIN_TEXT_LENGTH

        logger.info(f"文本PDF解析完成, 文字数量: {text_length}, OCR开关: {ocr_enabled}, 最小文字阈值: {min_text_length}")

        # 第二步：若文字不足且OCR已启用，则调用OCR服务
        if text_length < min_text_length and ocr_enabled:
            logger.info(f"文字数量({text_length})低于阈值({min_text_length})，开始调用OCR服务: {file_path}")
            ocr_result = scanPdf2info(file_path)
            print(ocr_result)
            if ocr_result.get("success", False):
                return ocr_result
            else:
                logger.warning(f"OCR服务解析失败: {ocr_result.get('error', '未知错误')}，回退使用文本解析结果")

        # 返回文本解析结果（文字充足 或 OCR未启用 或 OCR失败时回退）
        return text_result

    except Exception as e:
        logger.error(f"文件处理异常: {str(e)}")
        return {'error': str(e)}
