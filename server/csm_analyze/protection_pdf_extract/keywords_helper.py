# 需求：从第一页找到【报告时间】，找到等级测评结论页，提取【测评结论】与【综合得分】
# 只有word转换成pdf的才可以识别，其他一律不识别
import os
import re
import fitz
from server.csm_analyze.protection_pdf_extract.helper import sort_block, contain_key
import logging

logger = logging.getLogger(__name__)


class KeyWordsHelper:
    def __init__(self, pdf_path):
        self.file_name = os.path.basename(pdf_path)
        self.first_page = 1
        self.djcpjl_page = 0  # 等级测评结论那一页
        self.report_time = ""  # 报告时间
        self.cpjl = ""  # 测评结论
        self.score = ""  # 综合得分
        try:
            self.doc = fitz.open(pdf_path)
            if self.doc is None or self.doc.page_count < 1:
                logger.error(f"【{self.file_name}】 文件存在问题，无法读取!!!")
                return
            self.total_page_num = self.doc.page_count
            self.__find_djcpjl_page()
            self.report_time = self.__extract_report_time()
            self.cpjl, self.score = self.__extract_cpjl_and_score()
        finally:
            self.doc.close()

    # 找到等级测评结论那一页，提取等级测评结论与得分
    # 找到逻辑， 先找到第一个总体评价的页码，然后找等级测评结论的页码，要< 总体评价
    def __find_djcpjl_page(self):
        # 总体评价页
        ztpj_page = self.__locate_target_page("总体评价")
        # 等级测评结论页
        djcpjl_page = self.__locate_target_page("等级测评结论")
        if ztpj_page == 0 or djcpjl_page == 0:
            return
        elif djcpjl_page >= ztpj_page:
            return
        else:
            self.djcpjl_page = djcpjl_page

    # 获取目标页的文本
    def __get_target_page_text(self, page_num: int) -> str:
        page = self.doc.load_page(page_num - 1)
        text = page.get_text("text")
        text = text.replace(" ", "").replace("\t", "")
        return text

    def __locate_target_page(self, keyword: str) -> int:
        for index in range(0, self.total_page_num):
            page = self.doc.load_page(index)
            all_text = page.get_text("text")
            if contain_key(all_text, keyword):
                return index + 1
        return 0

    # 提取报告时间
    def __extract_report_time(self) -> str:
        text = self.__get_target_page_text(self.first_page)
        pattern = r"报告时间：(\d{4}年\d{2}月\d{2}日)"
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        else:
            return ""

    # 提取测评结论 与 综合得分
    def __extract_cpjl_and_score(self) -> tuple[str, str]:
        page = self.doc.load_page(self.djcpjl_page - 1)
        tables = page.find_tables().tables
        if len(tables) < 1:
            return "", ""

        table = tables[0]
        text_list = table.extract()
        if len(text_list) < 1:
            return "", ""
        # ['测评结论', None, '基本符合', '综合得分', '89.9', None]
        last_line = text_list[-1]
        last_line = [x for x in last_line if x is not None]
        if len(last_line) < 2:
            return "", ""
        elif len(last_line) == 4:
            return last_line[1], last_line[3]
        else:
            return "", ""


def single_test():
    pdf_path = r"C:\Users\Administrator\Desktop\2018泉州供电公司调度自动化系统信息安全等级测评报告-S2A3G3.pdf"

    oh = KeyWordsHelper(pdf_path)
    print(oh.report_time)
    print(oh.cpjl)
    print(oh.score)


if __name__ == "__main__":
    single_test()
