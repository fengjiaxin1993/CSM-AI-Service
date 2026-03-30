import json
from typing import Dict, Optional
import fitz
import re
import numpy as np
from rapidocr import RapidOCR
from wired_table_rec.main import WiredTableInput
from wired_table_rec import WiredTableRecognition
from server.warning_analysis.extract_info.helper import _init_structured_fields, html_to_table, clean_text
from server.utils import build_logger

logger = build_logger()


class ScannedPdfReportParser:
    """电力行业告警报告PDF扫描件解析器（使用RapidOCR）"""

    def __init__(
            self,
            pdf_path: str,
    ):
        """
        初始化扫描PDF解析器
        
        Args:
            pdf_path: PDF文件路径
        """
        try:
            self.pdf_path = pdf_path
            self.ocr_engine = RapidOCR(params={"Global.log_level": "critical"})
            self.wired_input = WiredTableInput()
            self.table_engine = WiredTableRecognition(self.wired_input)

            self.doc = fitz.open(self.pdf_path)
            self.structured_data = _init_structured_fields()
            self.pdf_ocr_result = self.__ocr_pdf()  # 每页存储ocr识别的相关信息
            self.full_text = self.__get_full_text()  # 根据ocr结构拼凑全文

            # 先提取表格信息（包括表格区域坐标）
            self.table_data_dict = self.__extract_table_dict()
        finally:
            self.doc.close()

    def __get_page(self, page):
        return self.doc.load_page(page - 1)

    def __to_img_array(self, page_num, dpi=600):
        page = self.__get_page(page_num)
        pix = page.get_pixmap(dpi=dpi)
        # 直接转换为numpy数组，不保存文件
        # pix.samples 是 RGB 格式的字节数据
        img_array = np.frombuffer(pix.samples, dtype=np.uint8)
        img_array = img_array.reshape(pix.height, pix.width, 3)  # RGB三通道
        # pix.save(f"./test-{page_num}.jpg")
        return img_array

    def __ocr_pdf(self):
        """使用 RapidOCR 识别 PDF 扫描件"""
        pdf_ocr_result = {}
        for page_num in range(1, self.doc.page_count + 1):
            img_array = self.__to_img_array(page_num)

            # OCR 识别
            rapid_ocr_output = self.ocr_engine(img_array, return_word_box=True)
            if rapid_ocr_output is not None:
                pdf_ocr_result[page_num] = rapid_ocr_output
        return pdf_ocr_result

    def __get_full_text(self):
        full_text = ""
        for page_num in range(1, self.doc.page_count + 1):
            rapid_ocr_output = self.pdf_ocr_result[page_num]
            if rapid_ocr_output and rapid_ocr_output.txts is not None:
                for txt in rapid_ocr_output.txts:
                    full_text += txt
        return clean_text(full_text)

    def __extract_table_dict(self) -> dict:
        """提取表格信息（第一页）"""
        try:
            image_array = self.__to_img_array(1, dpi=600)  #高精度
            rapid_ocr_output = self.ocr_engine(image_array, return_word_box=True)
            ocr_result = list(
                zip(rapid_ocr_output.boxes, rapid_ocr_output.txts, rapid_ocr_output.scores)
            )
            # 表格识别
            table_results = self.table_engine(image_array, ocr_result=ocr_result)
            html = table_results.pred_html
            # HTML转表格
            table = html_to_table(html)
            header_list = table[0]
            first_line = table[1]
            table_info = {}
            for i, header in enumerate(header_list):
                if i < len(first_line):
                    table_info[clean_text(header)] = clean_text(first_line[i])
            return table_info
        except Exception as e:
            logger.error(f"表格识别异常: {e}")
            return {}

    def __extract_section_content(self, section_name: str, next_section_name: Optional[str] = None) -> str:
        """提取指定模块的内容"""
        if not section_name and not next_section_name:
            return ""
        elif not section_name and next_section_name:
            pattern = rf"\s*(.+?)\s*{next_section_name}"
        elif section_name and not next_section_name:
            pattern = rf"{section_name}\s*(.+?)$"
        else:
            pattern = rf"{section_name}\s*(.+?)\s*{next_section_name}"

        match = re.search(pattern, self.full_text, re.DOTALL)
        if match:
            content = match.group(1).strip()
            content = re.sub(r"\s+", " ", content)
            return content
        return ""

    def parse(self) -> Dict:
        """执行完整解析流程"""
        # 1. 提取标题
        self.structured_data["报告标题"] = self.__extract_section_content("", "一、告警信息")
        # 2. 提取告警信息
        self.structured_data["告警信息"] = self.__extract_section_content("一、告警信息", "设备名称")
        # 提取表格信息
        self.structured_data["设备名称"] = self.table_data_dict.get("设备名称", "")
        self.structured_data["设备类型"] = self.table_data_dict.get("设备类型", "")
        self.structured_data["告警时间"] = self.table_data_dict.get("告警时间", "")
        self.structured_data["告警内容"] = self.table_data_dict.get("告警内容", "")
        # 3. 提取处置过程
        self.structured_data["处置过程"] = self.__extract_section_content("二、处置过程", "三、原因分析")
        # 4. 提取原因分析
        self.structured_data["原因分析"] = self.__extract_section_content("三、原因分析", "四、整改情况")
        # 5. 提取整改情况
        self.structured_data["整改情况"] = self.__extract_section_content("四、整改情况", "五、防范措施")
        # 6. 提取防范措施
        self.structured_data["防范措施"] = self.__extract_section_content("防范措施")
        return self.structured_data


# ---------------------- 测试代码 ----------------------
if __name__ == "__main__":
    # 测试PDF扫描件解析
    # SCANNED_PDF_PATH = "../test1.pdf"
    SCANNED_PDF_PATH = "../pdf-告警分析报告模板 -demo.pdf"

    # 使用 RapidOCR 识别
    parser = ScannedPdfReportParser(
        pdf_path=SCANNED_PDF_PATH
    )
    result = parser.parse()

    print("=== PDF扫描件RapidOCR解析结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
