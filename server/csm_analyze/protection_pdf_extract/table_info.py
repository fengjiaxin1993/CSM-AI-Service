from server.csm_analyze.protection_pdf_extract.helper import is_contain, area_percent, clean
import fitz.table


class CellInfo:
    def __init__(self, bbox):
        self.__bbox = bbox
        self.__content_list = []

    def fill_content(self, content):
        self.__content_list.append(clean(content))

    def get_bbox(self):
        return self.__bbox

    def get_content(self):
        return "".join(self.__content_list)


# pymupdf 是这样解析 合并单元格的，只在最小坐标的单元格有cell，并且cell的bbox为合并后的大小，其他为None
def get_matrix(rows: list[fitz.table.TableRow], row_count: int, col_count: int):
    matrix = [[None for _ in range(col_count)] for _ in range(row_count)]
    for i in range(row_count):
        row = rows[i]
        for j in range(col_count):
            cell = row.cells[j]
            if cell is None:
                continue
            else:
                matrix[i][j] = CellInfo(cell)
    return matrix


"""
使用pymypdf 解析出来的表格可能包含很多空列
第一页的table原始格式如下
[
    ['', '序号', '', '', '安全类', '', '', '安全问题', '', '', '关联资产', '', '', '关联威胁', '', '', '危害分析结果', '', '', '风险等级', ''],
    ['', '安全通用要求', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, ''],
    ['1', None, None, '安全区域边界', None, None, '未可信验证模块，无法基于可\n信根对通信设备的系统引导程\n序、系统程序、重要配置参数\n和通信应用程序等进行可信验\n证。', None, None, 'I-II 区横向边界、II-III\n区横向边界、I-III 区横\n向边界、主网-备调纵向\n边界', None, None, '恶意破坏\n系统设\n施、篡改', None, None, '边界设备不支持可信计算，不能保\n证系统和应用的完整性，软件栈受\n到攻击发生改变后不能及时发现，\n存在网络攻击、篡改、身份欺骗的\n风险。', None, None, '低', None, None],
    ['2', None, None, '安全计算环境(网\n络设备)', None, None, '设备不具有可信根芯片或硬\n件，目前暂不支持基于可信根\n对计算设备的系统引导程序、\n系统程序、重要配置参数和通\n信应用程序等进行可信验证。', None, None, 'II 区主干交换机1、备调\n主干交换机1、前置交换\n机1、II 区主干交换机\n2、I 区主干交换机1、备\n调主干交换机2、III 区\n主干交换机2、备调前置\n交换机2、备调前置交换\n机1、网络安全管理平台', None, None, '恶意破坏\n系统设\n施、篡改', None, None, '现有计算环境无法有效识别非授权\n软件，防止计算环境完整性受篡\n改；无法保证端应用行为可控；无\n法保证端网络身份可信，防止网络\n通信身份欺骗。', None, None, '低', None, None]
]
第二页的table原始格式如下
[
    ['', '序号', '', '', '安全类', '', '', '安全问题', '', '', '关联资产', '', '', '关联威胁', '', '', '危害分析结果', '', '', '风险等级', ''],
    ['', None, None, '', None, None, '', None, None, '组网交换机、I 区主干交\n换机2、III 区主干交换\n机1、I 区延伸交换机\n1、前置交换机2、I 区延\n伸交换机2', None, None, '', None, None, '', None, None, '', None, None], 
    ['3', None, None, '安全计算环境(安\n全设备)', None, None, '安全设备未设置可信根，不能\n基于可信根对系统引导程序、\n系统程序、重要配置参数和应\n用程序等进行可信验证。', None, None, '主站-备调纵向加密2、I\n区网络安全监测装置\n备、II 区运维权限管控\n防火墙、I-III 区正向隔\n离装置、I 区网络安全监\n测装置主、III 区网络安\n全监测装置主、I-II 防火\n墙A、I 区运维权限管控\n防火墙、I 区IPS 入侵防\n御设备、III 区防火墙', None, None, '恶意破坏\n系统设\n施、篡改', None, None, '现有计算环境无法有效识别非授权\n软件，防止计算环境完整性受篡\n改；无法保证端应用行为可控；无\n法保证端网络身份可信，防止网络\n通信身份欺骗。', None, None, '低', None, None]
]
总结出来的规律如下
1. 第一行是表头, 去掉空字符串即可
2. 第二行及以后的表格内容可能是空的,去掉None,表格准确
"""
def clean_table(table: list[list[str]]):
    header_col_num = len(table[0])
    header_col = table[0]
    row = len(table)
    valid_col_num = 0 # 有效列数
    for col in header_col:
        if col == '':
            continue
        else:
            valid_col_num += 1
    # 不需要处理
    if valid_col_num == header_col_num:
        return table

    new_table = [['' for _ in range(valid_col_num)] for _ in range(row)]

    # 处理表头
    valid_header_j = 0
    for col in header_col:
        if col == '':
            continue
        else:
            new_table[0][valid_header_j] = clean(col)
            valid_header_j += 1
    # 处理数据列
    for i in range(1, row):
        valid_j = 0
        for j in range(header_col_num):
            if table[i][j] == 'None' or table[i][j] is None:
                continue
            else:
                new_table[i][valid_j] = clean(table[i][j])
                valid_j += 1
    return new_table


# 存储TableInfo的详细信息
class TableInfo:
    def __init__(self, table: fitz.table.Table, mark_flag: bool, blocks: list,header_len:int):
        # ====1==== 获取表格的基本信息
        self.header_len = header_len
        self.mark_flag = mark_flag
        self.table = table
        self.extract_table = table.extract()
        # if self.header_len == len(self.extract_table[0]):
        self.table_data = self.extract_table
        # else:
        #     self.table_data = clean_table(self.extract_table)
        # 行列基本信息
        self.row_count = len(self.table_data)  # 行数
        self.col_count = len(self.table_data[0])  # 列数
        # 表格总体bbox坐标
        self.table_bbox = self.table.bbox
        # 划分表格的信息
        self.rows = self.table.rows
        # blocks信息
        self.blocks = blocks

    def __find_xy_index(self, text_bbox):  # 找出text_bbox在matrix的哪个单元格中 # 这个要优化，用最大面积的方式解决
        target_i = -1
        target_j = -1
        max_perc = 0
        for i in range(self.row_count):
            for j in range(self.col_count):
                cellInfo = self.matrix[i][j]
                if cellInfo is None:
                    continue
                else:
                    text_perc = area_percent(text_bbox, cellInfo.get_bbox())
                    if text_perc > max_perc:
                        target_i = i
                        target_j = j
                        max_perc = text_perc
        return target_i, target_j

    def __fill_cell(self, text_bbox, text):  # 根据text_bbox找到在表格的位置，将内容填充
        x_idx, y_idx = self.__find_xy_index(text_bbox)
        self.matrix[x_idx][y_idx].fill_content(text)

    def __fill_info(self):
        for block in self.blocks:
            type_info = block["type"]
            block_bbox = block['bbox']
            if type_info != 0:  # 非文字block
                continue
            if not is_contain(self.table_bbox, block_bbox, thresold=0):  # 不在表格block中的文字舍弃
                continue
            lines = block['lines']
            for line in lines:
                spans = line["spans"]
                dir = line["dir"]
                if dir[0] != 1.0 or dir[1] != 0.0:  # 去除倾斜方向的文字
                    continue
                for span in spans:
                    span_text = span["text"]
                    span_bbox = span["bbox"]
                    self.__fill_cell(span_bbox, span_text)

    # 没有水印，直接通过第三方库获取数据
    def __get_unmark_table_data(self):
        table = [['' for _ in range(self.col_count)] for _ in range(self.row_count)]
        for i in range(self.row_count):
            for j in range(self.col_count):
                text = self.table_data[i][j]
                if text is not None:
                    text = clean(text)
                    table[i][j] = text
        return table

    # 有水印，通过block，判断bbox进行填充
    def __get_mark_table_data(self):
        self.matrix = get_matrix(self.rows, self.row_count, self.col_count)
        self.__fill_info()
        table = [['' for _ in range(self.col_count)] for _ in range(self.row_count)]
        for i in range(self.row_count):
            for j in range(self.col_count):
                cellInfo = self.matrix[i][j]
                if cellInfo:
                    table[i][j] = cellInfo.get_content()
        # 去除空列
        table = clean_table(table)
        return table

    def get_table(self):
        if self.mark_flag:
            return self.__get_mark_table_data()
        else:
            return self.__get_unmark_table_data()
