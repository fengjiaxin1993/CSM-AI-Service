# 安全通用要求这一行是多列合并，需要删除
# 安全通用在表头下面
from server.csm_analyze.protection_pdf_extract.helper import contain_key, clean


def need_drop(line_list) -> bool:
    for line in line_list:
        if line:
            if contain_key(line, '安全通用要求'):
                return True
    return False


def clean_list(arr: list[str]):
    length = len(arr)
    for i in range(length):
        if arr[i] is None:
            arr[i] = ""
        else:
            arr[i] = clean(arr[i])


# 判断一行多列是否都有信息
def check_all_fill(line_list) -> bool:
    for txt in line_list:
        if not txt:
            return False
    return True


"""
在 PDF 中，页面的原点 (0,0) 处于 左下角。
在 MuPDF 中，页面的原点 (0,0) 处于 左上角。
"""


# page_bbox是整页的x0,y0,x1,y1坐标
# text_bbox是文本段的x0,y0,x1,y1坐标
# 该函数是获取text_bbox下面的所有区域
def get_below_bbox(page_bbox, text_bbox):
    page_x0, page_y0, page_x1, page_y1 = page_bbox
    text_x0, text_y0, text_x1, text_y1 = text_bbox
    return page_x0, text_y1, page_x1, page_y1


# page_bbox是整页的x0,y0,x1,y1坐标
# text_bbox是文本段的x0,y0,x1,y1坐标
# 该函数是获取text_bbox上面的所有区域
def get_upper_bbox(page_bbox, text_bbox):
    page_x0, page_y0, page_x1, page_y1 = page_bbox
    text_x0, text_y0, text_x1, text_y1 = text_bbox
    return page_x0, page_y0, page_x1, text_y0


# 通过blocks判断是否含有倾斜文字水印
def contain_mark(blocks):
    for block in blocks:
        type_info = block["type"]
        if type_info != 0:  # 非文字block
            continue
        lines = block['lines']
        for line in lines:
            dir = line["dir"]
            if dir[0] != 1.0 or dir[1] != 0.0:  # 去除倾斜方向的文字
                return True
    return False


def list_equal(list1, list2):
    if len(list1) != len(list2):
        return False
    for i in range(len(list1)):
        if list1[i] != list2[i]:
            return False
    return True


def header_valid(header_list):
    for line in header_list:
        if line is None or line == '':
            return False
    return True
