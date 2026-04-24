# # -*- coding: utf-8 -*-
# import json
# from typing import Dict, Optional, List
# import fitz
# import re
# import numpy as np
# from rapidocr import RapidOCR
# from wired_table_rec.main import WiredTableInput
# from wired_table_rec import WiredTableRecognition
# from server.csm_analyze.warning_analysis.extract_info.helper import _init_structured_fields, html_to_table, clean_text
# from server.utils import build_logger
#
# logger = build_logger()
#
# # 全局单例：OCR引擎和表格识别引擎
# _ocr_engine = None
# _table_engine = None
#
#
# def get_ocr_engine():
#     """获取全局OCR引擎单例"""
#     global _ocr_engine
#     if _ocr_engine is None:
#         _ocr_engine = RapidOCR(params={"Global.log_level": "critical"})
#     return _ocr_engine
#
#
# def get_table_engine():
#     """获取全局表格识别引擎单例"""
#     global _table_engine
#     if _table_engine is None:
#         wired_input = WiredTableInput()
#         _table_engine = WiredTableRecognition(wired_input)
#     return _table_engine
#
#
# class ScannedPdfReportParser:
#     """电力行业告警报告PDF扫描件解析器（使用RapidOCR）"""
#
#     def __init__(
#             self,
#             pdf_path: str,
#     ):
#         """
#         初始化扫描PDF解析器
#
#         Args:
#             pdf_path: PDF文件路径
#         """
#         self.pdf_path = pdf_path
#         self.ocr_engine = get_ocr_engine()
#         self.table_engine = get_table_engine()
#
#         self.doc = fitz.open(self.pdf_path)
#         self.structured_data = _init_structured_fields()
#         self.pdf_ocr_result = self.__ocr_pdf()  # 每页存储ocr识别的相关信息
#         self.full_text = self.__get_full_text()  # 根据ocr结构拼凑全文
#
#         # 先提取表格信息（包括表格区域坐标）
#         self.tables_data = self.__extract_tables()
#
#     def __get_page(self, page):
#         return self.doc.load_page(page - 1)
#
#     def __to_img_array(self, page_num, dpi=600):
#         page = self.__get_page(page_num)
#         pix = page.get_pixmap(dpi=dpi)
#         # 直接转换为numpy数组，不保存文件
#         # pix.samples 是 RGB 格式的字节数据
#         img_array = np.frombuffer(pix.samples, dtype=np.uint8)
#         img_array = img_array.reshape(pix.height, pix.width, 3)  # RGB三通道
#         # pix.save(f"./test-{page_num}.jpg")
#         return img_array
#
#     def __ocr_pdf(self):
#         """使用 RapidOCR 识别 PDF 扫描件"""
#         pdf_ocr_result = {}
#         for page_num in range(1, self.doc.page_count + 1):
#             img_array = self.__to_img_array(page_num)
#
#             # OCR 识别
#             rapid_ocr_output = self.ocr_engine(img_array, return_word_box=True)
#             if rapid_ocr_output is not None:
#                 pdf_ocr_result[page_num] = rapid_ocr_output
#         return pdf_ocr_result
#
#     def __get_full_text(self):
#         full_text = ""
#         for page_num in range(1, self.doc.page_count + 1):
#             rapid_ocr_output = self.pdf_ocr_result[page_num]
#             if rapid_ocr_output and rapid_ocr_output.txts is not None:
#                 for txt in rapid_ocr_output.txts:
#                     full_text += txt
#         return clean_text(full_text)
#
#     def __extract_tables(self) -> List[List[Dict]]:
#         """提取所有页面的表格信息，返回list[list[dict]]格式"""
#         tables_data = []
#         for page_num in range(1, self.doc.page_count + 1):
#             try:
#                 image_array = self.__to_img_array(page_num, dpi=600)  # 高精度
#                 rapid_ocr_output = self.ocr_engine(image_array, return_word_box=True)
#                 if rapid_ocr_output is None:
#                     continue
#                 ocr_result = list(
#                     zip(rapid_ocr_output.boxes, rapid_ocr_output.txts, rapid_ocr_output.scores)
#                 )
#                 # 表格识别
#                 table_results = self.table_engine(image_array, ocr_result=ocr_result)
#                 html = table_results.pred_html
#                 # HTML转表格
#                 table = html_to_table(html)
#                 if not table or len(table) == 0:
#                     continue
#
#                 # 转换为list[dict]格式
#                 table_data = []
#                 headers = [clean_text(h) for h in table[0]]
#                 for row_idx in range(1, len(table)):
#                     row = table[row_idx]
#                     row_dict = {}
#                     for col_idx, cell in enumerate(row):
#                         if col_idx < len(headers):
#                             header = headers[col_idx] if headers[col_idx] else f"列{col_idx+1}"
#                             row_dict[header] = clean_text(cell) if cell else ""
#                         else:
#                             row_dict[f"列{col_idx+1}"] = clean_text(cell) if cell else ""
#                     if row_dict:
#                         table_data.append(row_dict)
#
#                 if table_data:
#                     tables_data.append(table_data)
#             except Exception as e:
#                 logger.error(f"第{page_num}页表格识别异常: {e}")
#                 continue
#         return tables_data
#
#     def __extract_section_content(self, section_name: str, next_section_name: Optional[str] = None) -> str:
#         """提取指定模块的内容"""
#         if not section_name and not next_section_name:
#             return ""
#         elif not section_name and next_section_name:
#             pattern = rf"\s*(.+?)\s*{next_section_name}"
#         elif section_name and not next_section_name:
#             pattern = rf"{section_name}\s*(.+?)$"
#         else:
#             pattern = rf"{section_name}\s*(.+?)\s*{next_section_name}"
#
#         match = re.search(pattern, self.full_text, re.DOTALL)
#         if match:
#             content = match.group(1).strip()
#             content = re.sub(r"\s+", " ", content)
#             return content
#         return ""
#
#     def __get_first_table_value(self, key: str, default: str = "") -> str:
#         """从第一个表格中获取指定键的值"""
#         if self.tables_data and len(self.tables_data) > 0:
#             first_table = self.tables_data[0]
#             if first_table and len(first_table) > 0:
#                 first_row = first_table[0]
#                 return first_row.get(key, default)
#         return default
#
#     def parse(self) -> Dict:
#         """执行完整解析流程"""
#         # 1. 提取标题
#         self.structured_data["报告标题"] = self.__extract_section_content("", "一、告警信息")
#         # 2. 提取告警信息
#         self.structured_data["告警信息"] = self.__extract_section_content("一、告警信息", "设备名称")
#         # 提取表格信息（从第一个表格的第一行）
#         self.structured_data["设备名称"] = self.__get_first_table_value("设备名称")
#         self.structured_data["设备类型"] = self.__get_first_table_value("设备类型")
#         self.structured_data["告警时间"] = self.__get_first_table_value("告警时间")
#         self.structured_data["告警内容"] = self.__get_first_table_value("告警内容")
#         # 3. 提取处置过程
#         self.structured_data["处置过程"] = self.__extract_section_content("二、处置过程", "三、原因分析")
#         # 4. 提取原因分析
#         self.structured_data["原因分析"] = self.__extract_section_content("三、原因分析", "四、整改情况")
#         # 5. 提取整改情况
#         self.structured_data["整改情况"] = self.__extract_section_content("四、整改情况", "五、防范措施")
#         # 6. 提取防范措施
#         self.structured_data["防范措施"] = self.__extract_section_content("防范措施")
#         return self.structured_data
#
#
# # ---------------------- 测试代码 ----------------------
# if __name__ == "__main__":
#     # 测试PDF扫描件解析
#     # SCANNED_PDF_PATH = "../test1.pdf"
#     SCANNED_PDF_PATH = "../pdf-告警分析报告模板 -demo.pdf"
#
#     # 使用 RapidOCR 识别
#     parser = ScannedPdfReportParser(
#         pdf_path=SCANNED_PDF_PATH
#     )
#     result = parser.parse()
#
#     print("=== PDF扫描件RapidOCR解析结果 ===")
#     print(json.dumps(result, ensure_ascii=False, indent=2))
