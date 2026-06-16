# 识别pdf扫描件 markdown格式的服务
"""
RapidDoc 服务 - 支持并发限制为 3
提供 PDF 解析 API，返回 OCR 结果和 bbox 信息
"""
import gc
import logging
import time
from typing import List
import fitz  # PyMuPDF
from fastapi import Body
from rapid_doc import RapidDocOutput
from csm_ai_service.server.ocr.ocr_helper import _convert_pdf_to_images, images_to_bytes_list

# 屏蔽 rapid_doc 及其相关库的日志
logging.getLogger("faiss").setLevel(logging.ERROR)
logging.getLogger("rapid_doc").setLevel(logging.ERROR)
logging.getLogger("rapid_doc.cli.common").setLevel(logging.ERROR)  # "end_page_id is out of range" 警告
logging.getLogger("rapid_doc.cli.tools").setLevel(logging.ERROR)
logging.getLogger("rapid_doc.utils").setLevel(logging.ERROR)
logging.getLogger("rapidocr").setLevel(logging.ERROR)
logging.getLogger("rapid_table").setLevel(logging.ERROR)
logging.getLogger("rapid_layout").setLevel(logging.ERROR)
logging.getLogger("onnxruntime").setLevel(logging.ERROR)
from csm_ai_service.server.protection_audit.tools.ocr_tools import handle_rapidDocOutputs
from csm_ai_service.server.ocr.single_ocr_engine import get_rapid_doc_engine
import os
from typing import Dict
from csm_ai_service.settings import Settings
from csm_ai_service.server.utils import build_logger
logger = build_logger()

DPI = Settings.basic_settings.PDF_DPI
BATCH_SIZE = 2  # 每批处理的页数，可根据内存/显存情况调整（遇到 OOM 请降低）


def startup_event():
    """启动时预热模型"""
    logger.info("服务启动，开始预热模型...")
    # 同步等待预热完成，确保服务启动后再接收请求
    preload_model()


def preload_model():
    """预热模型（在后台运行）"""
    try:
        get_rapid_doc_engine()
        logger.info("模型初始化完成，服务已就绪")
    except Exception as e:
        logger.error(f"模型预热失败: {e}")


def _ocr_pages_in_batches(bytes_list: List[bytes], total_pages: int) -> List[RapidDocOutput]:
    """
    分批调用 RapidDoc，避免一次性把所有页面塞入内存导致 OOM。

    每批处理 BATCH_SIZE 页，处理完释放中间数据再继续下一批。
    """
    engine = get_rapid_doc_engine()
    all_outputs = []

    for batch_start in range(0, total_pages, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_pages)
        batch = bytes_list[batch_start:batch_end]
        logger.info(
            f"OCR 分批处理: 第 {batch_start + 1}-{batch_end} 页 / 共 {total_pages} 页"
        )

        batch_outputs = engine(inputs=batch)
        all_outputs.extend(batch_outputs)

        # 释放该批次的中间数据，帮助 GC 回收
        del batch_outputs
        gc.collect()

    return all_outputs


def pdf2info(
        file_path: str = Body(None, embed=True, description="文件路径")
):
    """
    只做OCR识别，不做任何前置校验

    - **file**: PDF 文件
    - **return_markdown**: 是否返回 Markdown
    """
    file_name = os.path.basename(file_path)
    total_pages = 0
    with fitz.open(file_path) as doc:
        total_pages = doc.page_count

    logger.info(f"调用pdf2info方法, file_name:{file_name}, 总页数:{total_pages}")
    result = {
        "success": False,
        "processing_time": 0.0,
        "markdown_text": "",
        "locate_json_result": {},
        "structure_json_result": {},
        "error": ""
    }

    # 对于超大 PDF，先估算内存
    if total_pages > BATCH_SIZE:
        logger.warning(
            f"PDF 页数较多 ({total_pages} 页)，将分批处理，每批 {BATCH_SIZE} 页"
        )

    start_time = time.time()
    try:
        # 步骤1: PDF 转图片（已有多线程并行 + 尺寸限制保护）
        images = _convert_pdf_to_images(file_path, dpi=DPI)
        if not images:
            result["error"] = "PDF 转换图片失败"
            return result

        bytes_list = images_to_bytes_list(images)

        # 立即释放 images（numpy 数组占内存很大）
        del images
        gc.collect()

        # 步骤2: 分批调用 RapidDoc，防止一次性 OOM
        outputs = _ocr_pages_in_batches(bytes_list, total_pages)

        # 释放 bytes_list
        del bytes_list
        gc.collect()

        # 步骤3: 合并结果
        res_dic = handle_rapidDocOutputs(outputs)

        # 释放 outputs
        del outputs
        gc.collect()

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
