import logging
from typing import Dict, List, Optional, Any
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from bs4 import BeautifulSoup
import cv2
from rapid_doc import RapidDocOutput
import re
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

def get_doc_id(text, res_list):
    for res in res_list:
        if text in res["text"]:
            return res["doc_id"]
    return ""

def html_table_to_markdown(html_table):
    """
    把 RapidDoc 输出的 <table> 表格 转成 标准 Markdown 表格
    支持 rowspan / colspan 合并单元格
    """
    soup = BeautifulSoup(html_table, "html.parser")
    table = soup.find("table")
    if not table:
        return ""

    rows = table.find_all("tr")
    if len(rows) < 1:
        return ""

    # 处理跨行跨列核心逻辑
    row_span_map = []
    table_data = []

    for tr in rows:
        cells = tr.find_all(["td", "th"])
        current_row = []
        col_idx = 0

        # 填充跨行遗留单元格
        while col_idx < len(row_span_map) and row_span_map[col_idx] > 0:
            current_row.append(table_data[-1][col_idx])
            row_span_map[col_idx] -= 1
            col_idx += 1

        for cell in cells:
            text = cell.get_text(strip=True)
            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            # 处理跨列
            for _ in range(colspan):
                current_row.append(text)
                # 处理跨行
                if rowspan > 1:
                    while len(row_span_map) <= col_idx:
                        row_span_map.append(0)
                    row_span_map[col_idx] = rowspan - 1
                col_idx += 1

        table_data.append(current_row)

    # 生成标准 Markdown 表格
    md = []
    for i, row in enumerate(table_data):
        line = "| " + " | ".join(row) + " |"
        md.append(line)
        if i == 0:
            md.append("|" + "|".join(["---"] * len(row)) + "|")

    return "\n".join(md)


# 转换表格（自动识别 <table>...</table> 并替换）

def clean_html_tables_in_text(text):
    table_pattern = re.compile(r"<table.*?</table>", re.DOTALL)
    return table_pattern.sub(lambda m: html_table_to_markdown(m.group(0)), text)



def handle_rapidDocOutputs(outputs: List[RapidDocOutput]) -> Dict[str, Any]:
    total_markdown = ""
    for idx, output in enumerate(outputs):
        total_markdown += output.markdown
        total_markdown += "\n"

    final_markdown = clean_html_tables_in_text(total_markdown)
    structure_json_result = split_markdown(final_markdown)
    # 先markdown 结构化信息
    layout_res_list = []
    for idx, output in enumerate(outputs):
        middle_json = output.middle_json
        pdf_info_list = middle_json["pdf_info"]
        pdf_info = pdf_info_list[0]
        parsing_res_list = []
        page_idx = pdf_info["page_idx"]
        page_size = pdf_info["page_size"]  #[595,842]
        page_width = page_size[0]
        page_height = page_size[1]
        para_blocks = pdf_info["para_blocks"]
        for para_idx, block in enumerate(para_blocks):
            block_idx = 0
            lines = block.get("lines", [])
            for line in lines:
                spans = line.get("spans", [])
                for span in spans:
                    bbox = span["bbox"]
                    score = span["score"]
                    content = span["content"]
                    block_type = span["type"]
                    if block_type != "text":
                        continue
                    block_id = f"block_{page_idx}_{para_idx}_{block_idx}"
                    doc_id = get_doc_id(content, structure_json_result["structure_json_result"])
                    parsing_res_list.append({
                        "block_id": block_id,
                        "block_content": content,
                        "block_type": block_type,
                        "block_bbox": bbox,
                        "doc_id": doc_id,
                    })
                    block_idx += 1
        layout_res_list.append({
            "meta": {
                "page_idx": page_idx,
                "page_width": page_width,
                "page_height": page_height,
            },
            "parsing_res_list": parsing_res_list,
        })

    res = {
        "layoutParsingResults": {"layout_res_list": layout_res_list},
        "markdown": final_markdown,
        "structureJsonResults": structure_json_result
    }
    return res


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


headers_to_split_on = [
    ("#", "title"),
    ("##", "title"),
    ("###", "title"),
    ("####", "title"),
]


def split_markdown(content: str) -> Dict[str, Any]:
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    text_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )
    docs = text_splitter.split_text(content)
    res_list = []
    for idx, doc in enumerate(docs):
        dic = {}
        text = doc.page_content
        title = doc.metadata.get("title", "")
        if title == "":
            title = text.split("\n")[0]
        dic["title"] = title
        dic["text"] = text
        dic["doc_id"] = f"doc_{idx}"
        res_list.append(dic)
    res = {"structure_json_result": res_list}
    return res
