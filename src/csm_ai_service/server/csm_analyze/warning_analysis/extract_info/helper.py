import json
from typing import Dict
import re
# 表格由于结构化识别，总是出现问题，因此采用ocr的方法，解决表格识别问题
import warnings
import logging

logging.getLogger("DownloadModel").setLevel(logging.WARNING)
from json_repair import repair_json

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
        "告警是否违规": "",  # 判断告警是否违规
        "设备名称": "",  # 设备名称
        "设备类型": "",  # 设备类型
        "告警时间": "",  # 告警时间
        "告警内容": "",  # 告警内容
        "处置过程": "",  # 处置过程
        "原因分析": "",  # 原因分析
        "责任人员和责任单位处理": "",  # 责任人员处理
        "人员教育培训": "",  # 人员教育培训
        "整改情况": "",  # 整改情况
        "防范措施": ""  # 防范措施
    }


def output_standard_dict(dict_standard: dict, output_dict: dict) -> dict:
    result_dic = {}
    for k in dict_standard.keys():
        if k in output_dict:
            result_dic[k] = output_dict[k]
        else:
            result_dic[k] = ""
    return result_dic


def bbox_in_area(bbox, bbox_list):  # 判断bbox是否在表格的bbox中
    for table_bbox in bbox_list:
        table_x0, table_y0, table_x1, table_y1 = table_bbox
        x0, y0, x1, y1 = bbox
        if x0 >= table_x0 and y0 >= table_y0 and x1 <= table_x1 and y1 <= table_y1:
            return True
    return False


def clean_text(text):
    text = re.sub(r" ", "", text)  # 合并多余空格/换行
    text = re.sub(r"\n+", "\n", text)  # 去除转义字符
    return text



def html_table_to_info(html_table) -> dict:
    """
    把 RapidDoc 输出的 <table> 表格 转成 标准 Markdown 表格
    支持 rowspan / colspan 合并单元格
    """
    soup = BeautifulSoup(html_table, "html.parser")
    table = soup.find("table")
    if not table:
        return {}

    rows = table.find_all("tr")
    if len(rows) < 1:
        return {}

    # 处理跨行跨列核心逻辑
    row_span_map = []
    table_data = []

    for tr in rows:
        cells = tr.find_all(["td", "th"])
        current_row = []
        col_idx = 0

        # 填充跨行遗留单元格
        while col_idx < len(row_span_map) and row_span_map[col_idx] > 0:
            current_row.append(table_data[-1][col_idx])
            row_span_map[col_idx] -= 1
            col_idx += 1

        for cell in cells:
            text = cell.get_text(strip=True)
            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            # 处理跨列
            for _ in range(colspan):
                current_row.append(text)
                # 处理跨行
                if rowspan > 1:
                    while len(row_span_map) <= col_idx:
                        row_span_map.append(0)
                    row_span_map[col_idx] = rowspan - 1
                col_idx += 1

        table_data.append(current_row)

    # 生成标准 Markdown 表格
    table_info = {}
    if len(table_data) > 0:
        header_list = table_data[0]
        first_line = table_data[1]
        for i, header in enumerate(header_list):
            if i < len(first_line):
                table_info[clean_text(header)] = clean_text(first_line[i])
    return table_info


if __name__ == "__main__":
    bad_json_str = """
    {
  "报告标题": "关于110kVXX变3月13日告警情况说明",
  "告警信息": "2026年03月13日XX省调电力监控系统网络安全管理平台，收到XX地调110kVXX变监测装置发出的重要告警，具体告警如下：\n\n加固后，445端口未监听。",
  "告警是否违规": "是",
  "设备名称": "后台主机",
  "设备类型": "主机",
  "告警时间": "2026年3月13日10:29:10",
  "告警内容": "后台主机（XXX.XX.X.1）服务器开放了 SMB(445)服务端口。",
  "处置过程": "加固前，445端口处于开放状态：加固后，445端口未监听。",
  "原因分析": "生产控制区与管理信息区、安全接入区之间边界，禁止任何穿越的事件发生后，针对站内监测对象做了以下安全措施：\n\n1. 对所有系统进行全面扫，对已知漏洞进行了补丁更新，确保系统安全性；\n2. 配置防火墙，限制445等中高端口的访问。",
  "责任人员和责任单位处理": "对直接责任人张三给予通报批评、诫勉谈话、经济处罚，离岗参加网络安全专项培训，考核合格后方可返岗。\n对当班班组长/专责李给予通报批评、绩效扣分处理。",
  "人员教育培训": "无",
  "整改情况": "所有主机整改完成照片：\n\n1. 系统告警记录：\n2. 事件现场取证照片与整改完成照片：\n\n2026年3月14日，110kVXX站内运维人员联系XXXX后台 电脑程序厂家，在厂家运维工人员指导下检查了445服务端口，并进行了永久关闭。",
  "防范措施": "对所有系统进行全面扫描，对已知漏洞进行了补丁更新，确保系统安全性；\n配置防火墙，限制445等中高端口的访问；\n对五防电脑开放端口进行了查，五防电脑开放端口均为关闭状态。"
}
"""
    result = fix_llm_json_output(bad_json_str)
    print(result)
