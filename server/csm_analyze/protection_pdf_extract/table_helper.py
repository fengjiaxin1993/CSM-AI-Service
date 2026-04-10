# 从指定页码范围内 提取安全问题风险分析表，识别跨页表格
import fitz

from server.csm_analyze.protection_pdf_extract.table_utils import contain_mark, get_below_bbox, list_equal, check_all_fill, \
    need_drop, clean_list, get_upper_bbox, header_valid
from server.csm_analyze.protection_pdf_extract.helper import sort_block, contain_key
from server.csm_analyze.protection_pdf_extract.table_info import TableInfo


# 获取table数据，以列表的形式
def get_table_data(table: fitz.table.Table, mark_flag: bool, blocks: list, header_len: int = -1):
    table_info = TableInfo(table, mark_flag, blocks, header_len)
    return table_info.get_table()


class TableHelper:
    def __init__(self, pdf_path, start_page, end_page, start_chapter, end_chapter):
        self.pdf_path = pdf_path
        self.snap_tolerance = 3  # 默认是3, 大多数用6适配没问题, 只有极个别必须用4 中卫第四十七光伏电站电力监控系统_测评报告.pdf
        self.start_page = start_page
        self.end_page = end_page  # 需要确定end_page是否包含表格，包含的表格是否和之前表格相同
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter

        try:
            self.doc = fitz.open(self.pdf_path)
            self.mark_flag = self.__contain_mark()
            self.first_table_bbox = None
            self.__set_first_page_info() # 设置第一页的表格以及第一页表格的bbox信息
            self.snap_tolerance = self.__find_valid_snap() # 确定snap_tolerance
            first_table = self.__get_first_table()
            first_table_data = get_table_data(first_table, self.mark_flag, self.__get_blocks(self.start_page))
            self.header_list = first_table_data[0]
            self.column_num = len(self.header_list)
            self.data_list = []
            self.__handle_first_table_data(first_table_data)
            self.__handle_pages()
            self.__handle_last_page()
            self.merge_table = self.__merge_info()
        finally:
            self.doc.close()

    def __contain_mark(self):  # 判断是否包含水印
        page = self.__get_page(self.start_page)
        blocks = page.get_text("dict")['blocks']
        return contain_mark(blocks)

    def __get_blocks(self, page_num):
        page = self.__get_page(page_num)
        blocks = page.get_text("dict")['blocks']
        return blocks

    def __get_page(self, page):
        return self.doc.load_page(page - 1)

    def __get_page_bbox(self, page):
        page = self.__get_page(page)
        return page.rect

    def __get_tables(self, page: int, bbox: (float, float, float, float) = None):
        """
        获取bbox范围内的表格
        :param page:
        :param snap_tolerance:
        :param bbox:
        :return:
        """
        page = self.doc.load_page(page - 1)
        tables = page.find_tables(clip=bbox, snap_tolerance=self.snap_tolerance)
        return tables.tables

    def __get_bbox(self, page_num: int, key: str) -> (float, float, float, float):
        """
        获取包含text内容的bbox四元组信息
        按照位置从上往下开始寻找
        :param page_num:
        :param key:
        :return:
        """
        page = self.__get_page(page_num)
        blocks = page.get_text("blocks")
        # 进行排序，从上到下排序
        sorted_lst = sort_block(blocks)
        for x0, y0, x1, y1, text, _, _ in sorted_lst:
            if contain_key(text, key):
                return x0, y0, x1, y1

    def __set_first_page_info(self):
        """
        设定第一页的表格以及第一页表格的bbox信息
        :return:
        """
        # stage1, 获取 安全问题风险分析 下面的bbox
        text_bbox = self.__get_bbox(self.start_page, self.start_chapter)
        page_bbox = self.__get_page_bbox(self.start_page)
        target_bbox = get_below_bbox(page_bbox, text_bbox)
        # stage2 确定是否有表格,如果没有表格，那么从下一页提取
        tables = self.__get_tables(self.start_page, target_bbox)
        if len(tables) == 0:  # 表明首页没有表格
            self.start_page += 1
            self.first_table_bbox = None
        else:  # 首页有表格
            self.first_table_bbox = target_bbox

    def __find_valid_snap(self):
        """
        根据第一个表格确定合适的snap
        :return:
        """
        page = self.__get_page(self.start_page)
        snap_list = [3, 4, 5, 6, 7]
        for snap in snap_list:
            tables = page.find_tables(clip=self.first_table_bbox,snap_tolerance=snap)
            table = tables.tables[0]
            table_data = table.extract()
            header_list = table_data[0]
            if header_valid(header_list):
                return snap
        return snap_list[0]

    # 获取第一个表格
    def __get_first_table(self):
        tables = self.__get_tables(self.start_page, bbox=self.first_table_bbox)
        # tables是一个列表，只取第一个。
        table = tables[0]
        return table

    # 需要查看是否有安全通用要求
    def __handle_first_table_data(self, first_table_data):
        table = first_table_data[1:]
        for index, line_list in enumerate(table):
            if index == 0 and need_drop(line_list):  # 多个单元格合并
                continue
            else:
                self.data_list.append(line_list)

    # 处理最后一页。最后一页 测评上面有表格就提取内容，没表格就忽略
    def __handle_last_page(self):
        # stage1, 获取 等保测评 上面的bbox
        text_bbox = self.__get_bbox(self.end_page, self.end_chapter)
        page_bbox = self.__get_page_bbox(self.end_page)
        target_bbox = get_upper_bbox(page_bbox, text_bbox)
        # stage2 确定是否有表格,如果没有表格,结束
        tables = self.__get_tables(self.end_page, target_bbox)
        if len(tables) != 0:
            table = tables[0]
            table_data = get_table_data(table, self.mark_flag, self.__get_blocks(self.end_page))
            if list_equal(self.header_list, table_data[0]):
                table_data = table_data[1:]
            for line_list in table_data:
                clean_list(line_list)
                self.data_list.append(line_list)

    def __handle_pages(self):
        for page in range(self.start_page + 1, self.end_page):
            tables = self.__get_tables(page)
            if len(tables) == 0:
                break
            else:
                table = tables[0]
                table_data = get_table_data(table, self.mark_flag, self.__get_blocks(page))
                if list_equal(self.header_list, table_data[0]):
                    table_data = table_data[1:]
                for line_list in table_data:
                    self.data_list.append(line_list)

    # 根据每一行信息，合并跨页表格(需要判断跨页的表格)
    def __merge_info(self) -> list[list[str]]:
        res = []
        for line_list in self.data_list:
            if len(res) == 0:
                res.append(line_list)
            else:
                # 最后一列
                risk_level = line_list[-1]
                if risk_level:  # 有风险等级，说明是一行数据
                    if check_all_fill(line_list):  # 每列都有信息
                        res.append(line_list)
                    else:  # 有的列没有信息
                        for col_idx in range(self.column_num):
                            if not line_list[col_idx]:
                                line_list[col_idx] = res[-1][col_idx]
                        res.append(line_list)
                else:  # 没有风险等级，说明需要和上一行合并
                    for col_idx in range(0, self.column_num - 1):
                        txt = line_list[col_idx]
                        if txt:
                            res[-1][col_idx] += txt
        return res


if __name__ == "__main__":

    #
    pdf_path = r"C:\Users\Administrator\Desktop\2018泉州供电公司调度自动化系统信息安全等级测评报告-S2A3G3.pdf"
    start_page = 146
    end_page = 150
    start_content = '安全问题风险评估'
    end_content = '等级测评结论'

    # pdf_path = r"D:\工作\科东\智能安全研发分部\CSM\csm本地安装\表格提取csm服务\等保测评所有文件\中卫第四十七光伏电站电力监控系统_测评报告.pdf"
    # start_page = 168
    # end_page = 186
    # start_content = '安全问题风险分析'
    # end_content = '等级测评结论'
    th = TableHelper(pdf_path, start_page, end_page, start_content, end_content)
    print(th.header_list)
    data_list = th.merge_table
    for line in data_list:
        print(line)
