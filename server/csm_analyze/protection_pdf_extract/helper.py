import hashlib
import math
import os
import re
from fastapi import UploadFile
import logging

from settings import Settings

logger = logging.getLogger(__name__)


# 字符串匹配，判断text中是否包含keyword
def contain_key(text, keyword):
    result_match = re.search(keyword, text)
    if result_match:
        return True
    else:
        return False


# 对blocks按照从上往下进行排序
# 解析下block信息 (x0,y0,x1,y1,text,blok_index,type)
# (x0,y0)是矩形的左上角 (x1,y1)是矩形的右下角
# block信息 (138.02000427246094, 240.28785705566406, 507.58001708984375, 252.81201171875, 'test', 9, 0)
# 将block从前往后进行排序
def sort_block(blocks):
    sorted_lst = sorted(blocks, key=lambda x: x[3])
    return sorted_lst


# 判断两个list内容是否相同
def is_same_list(a_list, b_list):
    len_a = len(a_list)
    len_b = len(b_list)
    if len_a != len_b:
        return False
    for index in range(len_b):
        a = a_list[index]
        b = b_list[index]
        if a != b:
            return False
    return True


# 将表格中关联资产进行分开
def split_line(header_list, data_list, split_char_list: list = list['、', '，'], key='关联资产'):
    column_num = len(header_list)
    column_idx = -1
    for idx in range(column_num):
        column_text = header_list[idx]
        if contain_key(column_text, key):
            column_idx = idx
            break
    assert column_idx != -1
    split_data_list = []
    for lines in data_list:
        assets = lines[column_idx]  # 关联资产
        asset_list = cut_list(assets, split_char_list)
        for asset in asset_list:
            copied_lines = lines[:]
            copied_lines[column_idx] = asset
            split_data_list.append(copied_lines)
    return split_data_list


def cut_list(line, split_char_list: list = list['、', '，']) -> list[str]:
    for char in split_char_list:
        lines = line.split(char)
        if len(lines) > 1:
            return lines
    return [line]


def calculate_skew(direction):
    x, y = direction[0], direction[1]
    # 弧度
    angle_rad = math.atan2(abs(y), abs(x))
    # 将角度转换为度数
    angle_deg = math.degrees(angle_rad)
    return angle_deg


# xlist 是从小到大排序
# 从xlist中找出最大的小于target的xlist中的下标
def fast_find(xlist, target):
    length = len(xlist)
    for idx in range(length - 1, -1, -1):
        if xlist[idx] < target:
            return idx
    return -1


# 判断两个bbox是否有交集
def is_intersect(bbox1, bbox2):
    a_x0, a_y0, a_x1, a_y1 = bbox1
    b_x0, b_y0, b_x1, b_y1 = bbox2
    if b_x0 >= a_x1 or b_x1 <= a_x0:
        return False
    if b_y0 >= a_y1 or b_y1 <= a_y0:
        return False
    return True


# 判断a_bbox是否包含 b_bbox
def is_contain(a_bbox, b_bbox, thresold: int = 15):
    a_x0, a_y0, a_x1, a_y1 = a_bbox
    b_x0, b_y0, b_x1, b_y1 = b_bbox
    if b_x0 + thresold >= a_x0 and b_y0 + thresold >= a_y0 and b_x1 <= a_x1 + thresold and b_y1 <= a_y1 + thresold:
        return True
    return False


def area_percent(a_bbox, b_bbox):  # 获取 a_bbox与b_bbox的交集面积/a_bbox
    a_x0, a_y0, a_x1, a_y1 = a_bbox
    b_x0, b_y0, b_x1, b_y1 = b_bbox
    # 完全没有交集
    if a_x1 < b_x0 or a_y1 < b_y0 or b_x1 < a_x0 or b_y1 < a_y0:
        return 0
    x0 = max(a_x0, b_x0)
    y0 = max(a_y0, b_y0)
    x1 = min(a_x1, b_x1)
    y1 = min(a_y1, b_y1)
    intersect_area = (x1 - x0) * (y1 - y0)
    a_area = (a_x1 - a_x0) * (a_y1 - a_y0)
    return intersect_area / a_area


def clean(txt: str):
    x = txt.strip()
    x = x.replace(" ", "")
    x = x.replace("\n", "")
    return x


def compute_str_md5(name: str) -> str:
    md5 = hashlib.md5()
    md5.update(name.encode('utf-8'))
    return md5.hexdigest()


# 保存，返回临时路径
def save_to_temp_file(file: UploadFile) -> str:
    file_content = file.file.read()  # 读取上传文件的内容
    prefix, suffix = os.path.splitext(file.filename)
    new_file_prefix = compute_str_md5(prefix)
    new_file_name = new_file_prefix + "." + suffix
    new_file_path = os.path.join(Settings.basic_settings.BASE_TEMP_DIR, new_file_name)
    if os.path.exists(new_file_path):
        os.remove(new_file_path)
    with open(new_file_path, "wb") as f:
        f.write(file_content)
    return new_file_path


def remove_dup_str(s):
    n = len(s)
    # 寻找最小重复单元
    for i in range(1, n // 2 + 1):
        if n % i == 0 and s[:i] * (n // i) == s:
            return s[:i]
    return s
