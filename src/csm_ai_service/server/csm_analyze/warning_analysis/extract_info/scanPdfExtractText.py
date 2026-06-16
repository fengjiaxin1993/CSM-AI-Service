import re

from csm_ai_service.server.csm_analyze.warning_analysis.extract_info.helper import _init_structured_fields, html_to_table, clean_text, \
    html_table_to_info
from csm_ai_service.server.ocr.single_ocr_engine import get_rapid_doc_engine
from csm_ai_service.server.utils import build_logger
logger = build_logger()
import logging
logging.getLogger("faiss").setLevel(logging.ERROR)
logging.getLogger("rapid_doc").setLevel(logging.ERROR)
logging.getLogger("rapid_doc.cli.common").setLevel(logging.ERROR)  # "end_page_id is out of range" 警告
logging.getLogger("rapid_doc.cli.tools").setLevel(logging.ERROR)
logging.getLogger("rapid_doc.utils").setLevel(logging.ERROR)
logging.getLogger("rapidocr").setLevel(logging.ERROR)
logging.getLogger("rapid_table").setLevel(logging.ERROR)
logging.getLogger("rapid_layout").setLevel(logging.ERROR)
logging.getLogger("onnxruntime").setLevel(logging.ERROR)

class SCANPDFExtractText:
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

        self.pdf_path = pdf_path
        self.structured_data = _init_structured_fields()
        self.markdown = self.__get_markdown_str()
        self.full_text = self.__get_full_text()  # 根据ocr结构拼凑全文
        # 先提取表格信息（包括表格区域坐标）
        self.table_data = self.__extract_table_dict()

    def __get_markdown_str(self):
        output = get_rapid_doc_engine()(inputs=self.pdf_path)
        markdown_str = output.markdown
        return markdown_str

    def __get_full_text(self):
        full_text = re.sub(r'<table.*?</table>', '', self.markdown, flags=re.DOTALL)
        return clean_text(full_text)

    def __extract_table_dict(self) -> dict:
        """提取表格信息（第一页）"""
        return html_table_to_info(self.markdown)

# ---------------------- 测试代码 ----------------------
if __name__ == "__main__":
    PDF_PATH1 = "../test_file/关于110kVXX变告警说明.pdf"
    PDF_PATH2 = "../test_file/附件1：关于A二级水电站2月3日的网络安全事件调查报告5 - v2【违规外联】.pdf"
    PDF_PATH3 = "../test_file/附件1：说明模板-关于XX变03月18日的告警情况说明-V2-WLAQ2026031801.pdf"
    PDF_PATH4 = "../test_file/附件1：说明模板-关于XX风光电厂）05月22日的告警情况说明5.31修改版本.pdf"
    parser = SCANPDFExtractText(PDF_PATH2)
    print(parser.full_text)
    print(parser.table_data)
