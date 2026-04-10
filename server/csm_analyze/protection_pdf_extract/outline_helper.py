# 找到 安全问题风险分析 所在页范围的方法类
import os
import re
import fitz
from server.csm_analyze.protection_pdf_extract.helper import sort_block, contain_key
import logging

logger = logging.getLogger(__name__)


# 抽取block_text信息
# block_text:
# 5 \n安全问题风险分析 ................ 132 \n
# return: ("5","安全问题风险分析",132)
def get_outline_block_info(block_text: str) -> (str, str, int):
    text = block_text.replace("\n", "")
    text = text.replace(" ", "")
    text = text.replace(".", "")
    text = text.strip()
    chapter_pattern = r'^\d+'  # 从头开始匹配首个数字
    page_pattern = r'\d+$'  # 从尾部开始匹配多个数字
    chapter_match = re.search(chapter_pattern, text)
    page_match = re.search(page_pattern, text)
    index_str = chapter_match.group()
    first_len = len(index_str)
    page_str = page_match.group()
    last_len = len(page_str)
    show_page_num = int(page_match.group())
    content = text[first_len:-last_len]
    return index_str, content, show_page_num


# 定位到一页中具体包含keyword的block-index信息
def locate_target_block_index(blocks, keyword):
    for idx, block in enumerate(blocks):
        text = block[4]
        if contain_key(text, keyword):
            return idx
    return -1


# 从start_index开始寻找，如果解析出来的chapter = target_chapter
def get_chapter_block_index(blocks, start_index, keyword):
    for idx in range(start_index + 1, len(blocks)):
        if contain_key(blocks[idx][4], keyword):
            return idx
    return -1


def get_match_num(blocks, key):
    res = 0
    for block in blocks:
        if contain_key(block[4], key):
            res += 1
    return res



def is_outline_chapter(blocks) -> bool:
    """
    思路:获取原始信息,合并在同一个line中相同font_size的字体, 主要解决 目 录这种问题
    :param blocks:
    :return:
    """

    block_list = []
    for idx, block in enumerate(blocks):
        type = block['type']
        bbox = block['bbox']
        if type == 0:  # 只保留文本信息
            lines = block["lines"]
            for line in lines:
                spans = line['spans']
                direction = line["dir"]  # 获取文字方向向量
                if direction[0] != 1.0 or direction[1] != 0.0:  # 去除倾斜方向的文字
                    continue
                font_text_list = merge_spans(spans)
                for font, text in font_text_list:
                    if text != '':
                        info = (bbox[0], bbox[1], bbox[2], bbox[3], text, font, type)
                        block_list.append(info)
    for block in block_list:
        text = block[4]
        font_size = block[5]
        if contain_key(text, '目录') and 14.0 <= font_size <= 18.0:
            return True
    return False


def get_spans_by_blocks(blocks) -> list[dict]:
    spans_list = []
    for idx, block in enumerate(blocks):
        type_int = block['type']
        if type_int == 0:  # 只保留文本信息
            lines = block["lines"]
            for line in lines:
                spans = line['spans']
                direction = line["dir"]  # 获取文字方向向量
                if direction[0] != 1.0 or direction[1] != 0.0:  # 去除倾斜方向的文字
                    continue
                spans_list.extend(spans)
    return spans_list


# 目录中每一条目的信息 #("5.1", "安全问题风险分析", 68)
class LineInfo:
    def __init__(self, chapter: str, title: str, page: int):
        self.chapter = chapter
        self.title = title
        self.page = page


# 给定候选目录条目列表，找出[安全问题风险分析]下一个条目
def get_next_line(infoList: list[LineInfo]) -> LineInfo:
    length = len(infoList)
    if length == 2:
        return infoList[1]
    start_page = infoList[0].page
    for i in range(1, length):
        line = infoList[i]
        if line.page > start_page:
            return line


# page种的block是否含有关键字
def blocksContainKey(blocks, key):
    spans = get_spans_by_blocks(blocks)
    for span in spans:
        if contain_key(span['text'], key):
            return True
    return False


def merge_spans(spans):
    res = []
    for idx, span in enumerate(spans):
        size = span['size']
        text = span['text']
        text = text.replace(" ", "")
        if idx == 0:
            res.append((size, text))
        else:
            last_size, last_text = res[-1]
            if size == last_size:
                res[-1] = (size, last_text + text)
            else:
                res.append((size, text))
    return res


start_chapter_keys = ["安全问题风险分析", "安全问题风险评估"]
end_chapter_keys = ["等级测评结论"]


# pdf解析类帮助方法
class OutlineHelper:
    def __init__(self, pdf_path, start_chapter="安全问题风险", end_chapter="等级测评结论"):
        self.file_name = os.path.basename(pdf_path)
        # 最后在外部显示的信息
        self.start_page = 0  # 从1开始 安全问题风险 章节 开始所在页数
        self.end_page = 0  # 从1开始 安全问题风险分析 下一章节 开始所在页数

        self.start_chapter = start_chapter
        self.end_chapter = end_chapter

        try:
            self.doc = fitz.open(pdf_path)
            if self.doc is None or self.doc.page_count < 1:
                logger.error(f"【{self.file_name}】 文件存在问题，无法读取!!!")
                return

            self.total_page_num = self.doc.page_count
            self.outline_start_page = self.__get_outline_start_page()
            self.outline_end_page = self.__get_outline_end_page()
            # debug
            if self.outline_start_page == 0:
                logger.error(
                    f"【{self.file_name}】 无法读取目录页!!!!")
                return

            show_page_num, actual_page_num = self.__get_show_info()
            self.difference = actual_page_num - show_page_num  # 表示实际页数和显示页数的差距，例如显示第1页，在pdf中是第10页，difference=9

            self.start_chapter, self.end_chapter, self.start_page, self.end_page = self.__get_target_page_info()
            logger.info(
                f"【{self.file_name}】的解析信息如下:\n【目录页信息】 开始页:{self.outline_start_page}\t结束页:{self.outline_end_page}\n"
                f"【解析信息】 开始章节:{self.start_chapter} 开始页码:{self.start_page}\t结束章节:{self.end_chapter} 结束页码:{self.end_page}")
        finally:
            self.doc.close()

    # 获取 显示的页码实际对应的页码index, 例如显示第1页，在pdf中第10页，返回10
    def __get_actual_page(self, show_page_num):
        return self.difference + show_page_num

    def is_valid(self):
        if self.start_page == 0 or self.end_page == 0:
            return False
        return True

    # 找出(显示第几页，实际第几页)
    # 有些文档正文不是从第一页开始,例如 SA-MI07-HT24031-CP24705_张易第一风电场电力监控系统_测评报告.pdf
    def __get_show_info(self) -> (int, int):
        for index in range(self.outline_end_page,
                           min(self.outline_end_page + 40, self.total_page_num - 1)):  # 目录结束后最多找40页
            page = self.doc.load_page(index)  # 目录结束后的第一页
            text = page.get_text("text")
            pattern = r"第(\d+)页"

            replace_text = text.replace(" ", "")
            lines = replace_text.split("\n")
            for line in lines:
                match = re.search(pattern, line)
                if match:
                    return int(match.group(1)), index + 1
                else:
                    continue
        return 1, self.outline_end_page + 1  # 找不到的话，默认是第一页

        # for index in range(int(0.5 * self.total_page_num)):
        #     blocks = self.__get_origin_blocks_by_page_index(index)
        #     spans = get_spans_by_blocks(blocks)
        #     for span in spans:
        #         if is_main_text_footer(span):
        #             return index + 1
        # return 0

    # 思路: v1第一页目录包含三个目录关键字
    # v2 判断目录所在位置，至少应该在页面上方，1/4处
    # 返回目录起始页
    def __get_outline_start_page(self) -> int:
        """
        思路: v1第一页目录包含三个目录关键字
             v2 判断目录所在位置，至少应该在页面上方，1/4处
        :return: 返回目录起始页码
        """
        for page_index in range(0, int(0.5 * self.total_page_num)):
            blocks = self.__get_origin_blocks_by_page_index(page_index)
            if is_outline_chapter(blocks):
                return page_index + 1
        return 0

    def __get_outline_end_page(self) -> int:
        """
        思路: 从找到的目录页开始遍历,直到第一个不含目录的页数
        :return: 目录结束页
        """

        for page_index in range(self.outline_start_page, self.outline_start_page + 200):  # 目录200页怎么也够了
            blocks = self.__get_origin_blocks_by_page_index(page_index)
            contain_flag = blocksContainKey(blocks, "目录")
            if contain_flag:
                continue
            else:
                return page_index

    def __get_blocks_by_page_index(self, page_index):
        """
        获取更详细的block文字信息
        去除倾斜的水印信息
        :param page_index:
        :return: (x0,y0,x1,y1,text,font_size,type)
        """
        page = self.doc.load_page(page_index)
        blocks = page.get_text("dict")['blocks']
        block_list = []
        for idx, block in enumerate(blocks):
            type = block['type']
            bbox = block['bbox']
            merge_text = ''
            if type == 0:  # 只保留文本信息
                lines = block["lines"]
                for line in lines:
                    spans = line['spans']
                    direction = line["dir"]  # 获取文字方向向量
                    if direction[0] != 1.0 or direction[1] != 0.0:  # 去除倾斜方向的文字
                        continue
                    for span in spans:
                        text = span['text']
                        merge_text += text
                info = (bbox[0], bbox[1], bbox[2], bbox[3], merge_text, idx, type)
                if merge_text != '':
                    block_list.append(info)
        return block_list

    def __get_origin_blocks_by_page_index(self, page_index):
        page = self.doc.load_page(page_index)
        return page.get_text("dict")['blocks']

    # 根据目录所在页数，确定 “安全问题风险分析” 所在的页数index
    def __locate_target_page(self, keyword: str) -> int:
        for index in range(self.outline_start_page - 1, self.outline_end_page):
            page = self.doc.load_page(index)
            all_text = page.get_text("text")
            if contain_key(all_text, keyword):
                return index
        return -1

    # 获取 安全问题风险分析 章节 所在的页码
    # 落地思路：最终目标找到 安全问题风险分析所在的实际页数
    # 1. 找到目录所在的实际页码范围
    # 2. 确定文件中显示的页码 和 实际对应的页码关系
    # 3. 找到 安全问题风险分析 在目录范围内的具体某一页
    # 4. 在该页中，找到 安全问题风险分析 在哪个block
    # 5. 找到下一个章节的block
    # 6. 找出开始，结束block对应的页码
    # 7. 根据显示页码信息，给出对应的实际页码范围
    def __get_target_page_info(self) -> (str, str, int, int):
        # stage 3 安全问题风险分析 在目录范围内的具体某一页
        risk_page_index = self.__locate_target_page(self.start_chapter)
        # stage 4 在该页中，找到 安全问题风险分析 在哪个block
        blocks = self.__get_blocks_by_page_index(risk_page_index)
        risk_block_index = locate_target_block_index(blocks, self.start_chapter)
        # stage 5 找到下一个章节的block
        next_chapter_block_index = get_chapter_block_index(blocks, risk_block_index, self.end_chapter)
        lineInfoList = []
        for i in range(risk_block_index, next_chapter_block_index + 1):
            block = blocks[i]
            block_text = block[4]
            chapter, title, page = get_outline_block_info(block_text)
            lineInfoList.append(LineInfo(chapter, title, page))
        nextLineInfo = get_next_line(lineInfoList)
        # stage 6 找出开始，结束block对应的页码
        riskLineInfo = lineInfoList[0]
        risk_chapter, risk_title, risk_page = riskLineInfo.chapter, riskLineInfo.title, riskLineInfo.page
        next_chapter, next_title, next_page = nextLineInfo.chapter, nextLineInfo.title, nextLineInfo.page
        # stage 7 根据显示页码信息，给出对应的实际页码范围
        actual_start_page = self.__get_actual_page(risk_page)
        actual_end_page = self.__get_actual_page(next_page)
        return risk_title, next_title, actual_start_page, actual_end_page


def dir_test():
    # 无水印 ok
    base_dir = "../files/unmark"
    # base_dir = "../files/mark"
    for filename in os.listdir(base_dir):
        pdf_path = os.path.join(base_dir, filename)
        oh = OutlineHelper(pdf_path)
        start_page = oh.start_page
        end_page = oh.end_page
        start_chapter = oh.start_chapter
        end_chapter = oh.end_chapter
        print(f"{filename} \n 起始页-结束页[{start_page} - {end_page}]")
        print("-------------------")


def single_test():
    pdf_path = r"C:\Users\Administrator\Desktop\2018泉州供电公司调度自动化系统信息安全等级测评报告-S2A3G3.pdf"

    oh = OutlineHelper(pdf_path)
    print(f"起始页-结束页[{oh.start_page} - {oh.end_page}]")
    print(f"起始章节-结束章节[{oh.start_chapter} - {oh.end_chapter}]")


if __name__ == "__main__":
    single_test()
    # dir_test()
