import fitz
import re
import json
from typing import Dict, Optional

from server.warning_analysis.extract_info.helper import _init_structured_fields, bbox_in_area, clean_text


class PDFExtractText:
    """电力行业告警报告PDF解析器（适配指定Word模板）,由word转换得到的pdf结构化文件"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(self.pdf_path)
        self.tables_data = self.__extract_tables()  # 1.先读取table数据
        self.full_text = self.__read_pdf()  # 2.跳过table, 读取全文

    def __extract_tables(self) -> list:
        """提取表格数据，返回list[list[dict]]格式"""
        tables_data = []
        for page_idx in range(self.doc.page_count):
            page = self.doc.load_page(page_idx)
            tables = page.find_tables()
            for table in tables.tables:
                table_data = []
                # 获取表格的所有行
                rows = table.extract()
                if rows and len(rows) > 0:
                    # 第一行作为表头
                    headers = rows[0]
                    # 遍历数据行
                    for row_idx in range(1, len(rows)):
                        row = rows[row_idx]
                        row_dict = {}
                        for col_idx, cell in enumerate(row):
                            if col_idx < len(headers):
                                header = headers[col_idx] if headers[col_idx] else f"列{col_idx + 1}"
                                row_dict[header] = cell if cell else ""
                            else:
                                row_dict[f"列{col_idx + 1}"] = cell if cell else ""
                        if row_dict:
                            table_data.append(row_dict)
                if table_data:
                    tables_data.append(table_data)
        return tables_data

    def __read_pdf(self) -> str:
        """读取PDF全文，越过表格数据"""
        bbox_list = []  # 表格边框坐标
        # 从所有页面获取表格的bbox
        for page_idx in range(self.doc.page_count):
            page = self.doc.load_page(page_idx)
            tables = page.find_tables()
            for table in tables.tables:
                bbox_list.append(table.bbox)

        full_text = ""
        for page_idx in range(self.doc.page_count):
            page = self.doc.load_page(page_idx)
            blocks = page.get_text("dict")['blocks']
            for idx, block in enumerate(blocks):
                type_int = block['type']
                if type_int == 0:  # 只保留文本信息
                    lines = block["lines"]
                    for line in lines:
                        spans = line['spans']
                        direction = line["dir"]  # 获取文字方向向量
                        if direction[0] != 1.0 or direction[1] != 0.0:  # 去除倾斜方向的文字
                            continue
                        for span in spans:
                            bbox = span['bbox']
                            if not bbox_in_area(bbox, bbox_list):
                                full_text += span["text"]
                full_text += "\n"
        full_text = clean_text(full_text)
        return full_text.strip()


# ---------------------- 测试代码 ----------------------
if __name__ == "__main__":
    # 测试PDF解析（word转换成的PDF）
    PDF_PATH1 = "../test_file/关于110kVXX变告警说明.pdf"
    PDF_PATH2 = "../test_file/附件1：关于A二级水电站2月3日的网络安全事件调查报告5 - v2【违规外联】.pdf"
    PDF_PATH3 = "../test_file/附件1：说明模板-关于XX变03月18日的告警情况说明-V2-WLAQ2026031801.pdf"
    PDF_PATH4 = "../test_file/附件1：说明模板-关于XX风光电厂）05月22日的告警情况说明5.31修改版本.pdf"
    parser = PDFExtractText(PDF_PATH1)
    print(parser.full_text)
    print(parser.tables_data)
