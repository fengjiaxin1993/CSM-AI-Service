from typing import Dict
import re
# 表格由于结构化识别，总是出现问题，因此采用ocr的方法，解决表格识别问题
import warnings
import logging

# 1. 屏蔽所有警告（含你那条 FutureWarning）
warnings.filterwarnings("ignore")
# 2. 屏蔽所有日志
logging.basicConfig(level=logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)
import fitz  # PyMuPDF
import numpy as np
from bs4 import BeautifulSoup

# 关闭所有日志
logging.getLogger().setLevel(logging.ERROR)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).disabled = True
    logging.getLogger(name).setLevel(logging.ERROR)

# 关键库静音
logging.getLogger("rapidocr").disabled = True
logging.getLogger("wired_table_rec").disabled = True


def pdf_page_to_image(pdf_path, page_num, dpi=200):
    """
    使用PyMuPDF将PDF单页转换为图片（纯内存，不保存文件）

    Args:
        pdf_path: PDF文件路径
        page_num: 页码（从1开始）
        dpi: 图片分辨率

    Returns:
        numpy.ndarray: 转换后的图片数组（RGB格式）
    """
    doc = fitz.open(pdf_path)
    if doc.page_count < page_num:
        doc.close()
        raise ValueError(f"PDF总页数为{doc.page_count}，请求页码{page_num}超出范围")

    page = doc.load_page(page_num - 1)  # PyMuPDF页码从0开始
    pix = page.get_pixmap(dpi=dpi)
    doc.close()

    # 直接转换为numpy数组，不保存文件
    # pix.samples 是 RGB 格式的字节数据
    img_array = np.frombuffer(pix.samples, dtype=np.uint8)
    img_array = img_array.reshape(pix.height, pix.width, 3)  # RGB三通道

    return img_array


def html_to_table(html):
    """
    直接从 html 字符串提取表格 → 返回二维列表 [[行1],[行2]]
    稳定、不乱码、不报错
    """
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if not table:
        return []

    # 提取所有行
    rows = []
    for tr in table.find_all('tr'):
        # 提取每一列的文字
        cols = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
        rows.append(cols)
    return rows


def _init_structured_fields() -> Dict:
    """初始化结构化字段（对应模板模块）"""
    return {
        "报告标题": "",  # 报告标题（如“XX地调关于X月X日XX变的告警情况说明”）
        "告警信息": "",
        "设备名称": "",  # 设备名称
        "设备类型": "",  # 设备类型
        "告警时间": "",  # 告警时间
        "告警内容": "",  # 告警内容
        "处置过程": "",  # 处置过程
        "原因分析": "",  # 原因分析
        "整改情况": "",  # 整改情况
        "防范措施": ""  # 防范措施
    }


def bbox_in_area(bbox, bbox_list):  # 判断bbox是否在表格的bbox中
    for table_bbox in bbox_list:
        table_x0, table_y0, table_x1, table_y1 = table_bbox
        x0, y0, x1, y1 = bbox
        if x0 >= table_x0 and y0 >= table_y0 and x1 <= table_x1 and y1 <= table_y1:
            return True
    return False


def clean_text(text):
    text = re.sub(r" ", "", text)  # 合并多余空格/换行
    text = re.sub(r"\n", "", text)  # 去除转义字符
    return text
