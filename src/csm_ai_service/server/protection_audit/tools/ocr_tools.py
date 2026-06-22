from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from rapid_doc import RapidDocOutput
import re
from csm_ai_service.server.utils import build_logger
from csm_ai_service.server.protection_audit.text_pdf_parser import PdfParseResult

logger = build_logger()



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



def handle_pdfParseResult(result: PdfParseResult) -> Dict[str, Any]:
    total_markdown = result.markdown # 表格已经清理过了
    structure_json_result = split_markdown(total_markdown)
    # 先markdown 结构化信息
    layout_res_list = []
    for page in result.pages:
        parsing_res_list = []
        for block in page.blocks:
            doc_id = get_doc_id(block.text, structure_json_result["structure_json_result"])
            parsing_res_list.append({
                "block_id": block.block_id,
                "block_content": block.text,
                "block_type": block.block_type,
                "block_bbox": block.bbox,
                "doc_id": doc_id,
            })
        # 每页的信息
        layout_res_list.append({
            "meta": {
                "page_idx": page.page_num,
                "page_width": page.width,
                "page_height": page.height,
            },
            "parsing_res_list": parsing_res_list,
        })

    res = {
        "layoutParsingResults": {"layout_res_list": layout_res_list},
        "markdown": total_markdown,
        "structureJsonResults": structure_json_result
    }
    return res
