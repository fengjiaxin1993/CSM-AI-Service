from typing import Dict, List, Optional, Any
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor, as_completed
from csm_ai_service.server.utils import build_logger

logger = build_logger()


def _convert_single_page(args):
    """转换单页PDF为图片（用于多线程并行）"""
    pdf_path, page_num, dpi = args
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_num)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return page_num, np.array(img)
    finally:
        doc.close()


def _convert_pdf_to_images(pdf_path: str, dpi: int, max_workers: int = 4) -> List[np.ndarray]:
    """将PDF转换为图片列表（多线程并行）

    使用配置文件中的PDF_DPI值
    """

    try:
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        doc.close()

        if total_pages == 0:
            return []

        # 小文件直接串行，大文件并行
        if total_pages <= 2:
            images = []
            doc = fitz.open(pdf_path)
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                zoom = dpi / 72.0
                matrix = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                images.append(np.array(img))
            doc.close()
            return images

        # 多线程并行转换
        workers = min(max_workers, total_pages)
        results = {}
        tasks = [(pdf_path, i, dpi) for i in range(total_pages)]

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_convert_single_page, task): task[1] for task in tasks}
            for future in as_completed(futures):
                page_num, img_array = future.result()
                results[page_num] = img_array

        # 按页码顺序返回
        return [results[i] for i in range(total_pages)]

    except Exception as e:
        logger.error(f"PDF转换失败: {e}")
        return []


def images_to_bytes_list(images: List[np.ndarray]) -> List[bytes]:
    """将 List[np.ndarray] 转换为 List[bytes]（PNG 格式，多线程并行）"""

    def _encode_single(img):
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        _, encoded = cv2.imencode(".png", img_bgr)
        return encoded.tobytes()

    if len(images) <= 2:
        return [_encode_single(img) for img in images]

    with ThreadPoolExecutor(max_workers=min(4, len(images))) as executor:
        return list(executor.map(_encode_single, images))
