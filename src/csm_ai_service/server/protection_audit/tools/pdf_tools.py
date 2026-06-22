# pdf_tools.py
# PDF页面图片API - 用于前端精确定位与框

import os
import base64
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz  # PyMuPDF
import io
from PIL import Image
from csm_ai_service.settings import Settings
from csm_ai_service.server.utils import build_logger
logger = build_logger()


def pdf_page_to_base64(doc: fitz.Document, page_num: int) -> tuple:
    """将PDF页面转换为base64编码的PNG图像"""
    page = doc.load_page(page_num)

    # 获取页面原始尺寸（点）
    rect = page.rect
    # 计算矩阵（DPI缩放）
    matrix = fitz.Matrix(Settings.basic_settings.PDF_DPI / 72, Settings.basic_settings.PDF_DPI / 72)

    # 渲染页面
    pix = page.get_pixmap(matrix=matrix)

    # 转换为PIL Image
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    # 转换为base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    ocr_width = rect.width
    ocr_height = rect.height

    return img_base64, pix.width, pix.height, ocr_width, ocr_height


def get_pdf_pages(filepath: str) -> Dict[str, Any]:
    """
    获取PDF所有页面的图片（base64编码）和尺寸信息

    Args:
        filepath: PDF文件路径
        zoom_factor: 缩放因子，默认2.0（提高分辨率）

    Returns:
        {
            "success": True/False,
            "pages": [
                {
                    "page_num": 0,
                    "img_base64": "...",
                    "width": 1190,
                    "height": 1684,
                    "ocr_width": 595,
                    "ocr_height": 842
                },
                ...
            ],
            "total_pages": n,
            "error": "..." (如果失败)
        }
    """
    if not filepath:
        return {"success": False, "error": "文件路径为空", "pages": []}

    # 检查文件是否存在，如果不存在，尝试在当前项目的 uploads 目录中查找
    if not os.path.exists(filepath):
        logger.warning(f"原路径文件不存在: {filepath}")

    # 检查文件扩展名
    ext = os.path.splitext(filepath)[1].lower()
    if ext != '.pdf':
        return {"success": False, "error": "不是PDF文件", "pages": []}

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(filepath)
        pages_data = []

        for page_num in range(doc.page_count):
            img_base64, width, height, ocr_width, ocr_height = pdf_page_to_base64(
                doc, page_num
            )
            pages_data.append({
                "page_num": page_num,
                "img_base64": img_base64,
                "width": width,
                "height": height,
                "ocr_width": ocr_width,
                "ocr_height": ocr_height
            })
        doc.close()

        return {
            "success": True,
            "pages": pages_data,
            "total_pages": len(pages_data)
        }

    except ImportError:
        logger.error("PyMuPDF (fitz) 未安装")
        return {"success": False, "error": "PyMuPDF未安装", "pages": []}
    except Exception as e:
        logger.error(f"获取PDF页面失败: {str(e)}")
        return {"success": False, "error": str(e), "pages": []}
