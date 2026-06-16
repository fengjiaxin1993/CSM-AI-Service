import os
from typing import Dict, Any
from csm_ai_service.server.protection_audit.ocr.ocr_service import pdf2info
from csm_ai_service.server.utils import build_logger
logger = build_logger()



def process_file_ocr_by_path(file_path: str) -> Dict:
    """
    直接调用 OCR 服务解析文件（不处理缓存，由调用方自行管理）
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
        logger.info(f"开始OCR处理(无缓存): {file_path}")
        result = pdf2info(file_path)
        return result
    except Exception as e:
        logger.error(f"OCR处理异常: {str(e)}")
        return {'error': str(e)}
