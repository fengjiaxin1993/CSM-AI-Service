import json
from typing import Dict
import re
# 表格由于结构化识别，总是出现问题，因此采用ocr的方法，解决表格识别问题
import warnings
import logging

from csm_ai_service.server.utils import fix_llm_json_output

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


def init_report_json_data() -> Dict:
    """初始化报告结构化字段（中文键）"""
    return {
        "报告标题": "",
        "告警信息": "",
        "设备名称": "",
        "设备类型": "",
        "告警时间": "",
        "告警内容": "",
        "处置过程": "",
        "原因分析": "",
        "责任人员和责任单位处理": "",
        "人员教育培训": "",
        "整改情况": "",
        "佐证材料": "",
    }


def init_analyze_result_json_data() -> Dict:
    """初始化研判结论结构化字段（中文键）"""
    return {
        "audit_result": "需人工复核",
        "audit_details": "",
        "summary": "",
        "reject_reason": "",
        "power_suggestion": "",
    }


def output_standard_dict(template: dict, output_dict: dict) -> dict:
    """根据模板标准化输出，返回与模板同键的dict"""
    result_dic = {}
    for k in template.keys():
        if k in output_dict:
            result_dic[k] = output_dict[k]
        else:
            result_dic[k] = template[k] if template[k] else ""
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
"""
{
  "code": 200,
  "msg": "success",
  "data": {
    "report_title": "关于110kVXX变3月13日告警情况说明",
    "alert_content": "后台主机（XXX.XX.X.1）服务器开放了SMB（445）服务端口",
    "meta_info": {
      "报告标题": "关于110kVXX变3月13日告警情况说明",
      "告警信息": "2026年03月13日XX省调电力监控系统网络安全管理平台，收到XX地调110kVXX变监测装置发出的重要告警，具体告警如下：",
      "设备名称": "后台主机",
      "设备类型": "主机",
      "告警时间": "2026-03-13 10:29:10",
      "告警内容": "后台主机（XXX.XX.X.1）服务器开放了SMB（445）服务端口",
      "处置过程": "2026年3月13日13时20分，110kVXX变站内人员对后台主机（IP地址XXX.XXX.X.1）进行加固后，告警不再更新。",
      "原因分析": "2026年03月13日XXXX水泥公司根椐生产需要对停运的40000KVA二号变压器进行投运操作，其电站值班人张三在更换投入变压器过程中发现二号变压器电压过低，在进行调档后由于电脑分辨率过高无法找到关闭调档画面栏菜单而直接进行电脑重启，重启后，紧急告警上传至网络安全管理平台，告警内容为XX站后台主机(IP地址：XXX.XXX.X.1）服务器开放了SMB(445)服务端口。IP地址XXX.XXX.X.1为110kVXX站后台主机地址，操作系统版本为windowsXP，主机品牌为戴尔，归属于XX水泥有限公司，因该主机在前期监测对象接入工作中未按要求进行加固，导致操作系统重启后，SMB（445端口）服务开放，上传相关紧急告警至网络安全管理平台。",
      "责任人员和责任单位处理": "1.对直接责任人张三给予通报批评、诫勉谈话、经济处罚，离岗参加网络安全专项培训，考核合格后方可返岗。2.对当班班组长/专责李四给予通报批评、绩效扣分处理。3.对负有管理责任的部门负责人王五进行提醒约谈，督促切实履行管理职责。",
      "人员教育培训": "已对站内运维人员做了相关网络安全知识教育。对直接责任人张三给予通报批评、诫勉谈话、经济处罚，离岗参加网络安全专项培训，考核合格后方可返岗。对所有员工进行网络安全意识培训，提高对钓鱼邮件、恶意软件等威胁的认识。",
      "整改情况": "告警发生后，XX地调自动化立即通知了110kVXX站相关负责人，2026年3月14日110kVXX站内运维人员联系XXXX后台电脑程序厂家，在厂家运维工人员指导下检查445服务端口，CMD命令排查确认445端口自动开启，随后通过修改注册表和关闭服务，永久关闭了该端口，对该主机进行了加固，同时对五防电脑开放端口进行了检查，五防电脑开放端口均为关闭状态。具体操作步骤如下：\n1.在"开始"菜单中输入cmd并回车打开"命令提示符"，输入netstat-an指令并回车，这里显示445端口还打开着。\n2.在"开始"菜单中输入regedit并回车打开注册表编辑器，通过修改注册表进行关闭445端口。\n3.在注册表修编辑器中进入路径：\nHTTP\\HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\NetBT\\Parameters\n4.建立一个DWORD项，名称为SMBDeviceEnabled,将这个新创建的DWORD值的数值数据设置为0。445端口通常用于SMB（ServerMessageBlock）协议，其协议主要用于实现文件共享等功能，这里采用禁用SMB设备来关闭445端口。\n5.做完以上步骤再进入"服务"管理器进行445端口相关的服务关闭，右键计算机点击管理。\n点击"服务和应用程序"，然后双击"服务"进入服务窗口。\n下拉菜单栏找到名为"Server"、"Workstation"、"TCP/IPNetBIOSHelper"的服务，右键点击该服务选择"禁用"选项，之后双击进入该服务，在"常规"选项中，将"启动类型"改为禁止。\n8.重启电脑，点击"菜单"，在"运行"中打开输入cmd打开"命令提示符"，输入netstat-an指令进行查看端口，这里可以看到445端口已关闭。\n随后做了",
      "防范措施": "本次端口开放报警事件违反了《电力监控系统安全防护规定》（国家发改委令第27号，2025年施行）第11条：生产控制区与管理信息区、安全接入区之间边界，禁止任何穿越的通用网络服务，必须采取边界防护措施。第13条：生产控制区禁止采用高风险通用网络服务，应对外设与端口接入行为严格管控。已对站内运维人员做了相关网络安全知识教育。事件发生后，针对站内监测对象做了以下安全措施：1.对所有系统进行全面扫描，对所有已知漏洞进行了补丁更新，确保系统安全性，告警主机已无中高端口处于开放状态；2.配置防火墙，限制445等中高端口的访问；3.对所有员工进行网络安全意识培训，提高对钓鱼邮件、恶意软件等威胁的认识。"
    },
    "file_name": "关于110kVXX变告警说明.docx",
    "full_report": "关于110kVXX变3月13日告警情况说明\n告警信息\n2026年03月13日XX省调电力监控系统网络安全管理平台，收到XX地调110kVXX变监测装置发出的重要告警，具体告警如下：\n处置过程\n2026年3月13日13时20分，110kVXX变站内人员对后台主机（IP地址XXX.XXX.X.1）进行加固后，告警不再更新。\n原因分析\n2026年03月13日XXXX水泥公司根椐生产需要对停运的40000KVA二号变压器进行投运操作，其电站值班人张三在更换投入变压器过程中发现二号变压器电压过低，在进行调档后由于电脑分辨率过高无法找到关闭调档画面栏菜单而直接进行电脑重启，重启后，紧急告警上传至网络安全管理平台，告警内容为XX站后台主机(IP地址：XXX.XXX.X.1）服务器开放了SMB(445)服务端口。IP地址XXX.XXX.X.1为110kVXX站后台主机地址，操作系统版本为windowsXP，主机品牌为戴尔，归属于XX水泥有限公司，因该主机在前期监测对象接入工作中未按要求进行加固，导致操作系统重启后，SMB（445端口）服务开放，上传相关紧急告警至网络安全管理平台。\n整改情况\n告警发生后，XX地调自动化立即通知了110kVXX站相关负责人，2026年3月14日110kVXX站内运维人员联系XXXX后台电脑程序厂家，在厂家运维工人员指导下检查445服务端口，CMD命令排查确认445端口自动开启，随后通过修改注册表和关闭服务，永久关闭了该端口，对该主机进行了加固，同时对五防电脑开放端口进行了检查，五防电脑开放端口均为关闭状态。具体操作步骤如下：\n1.在"开始"菜单中输入cmd并回车打开"命令提示符"，输入netstat-an指令并回车，这里显示445端口还打开着。\n2.在"开始"菜单中输入regedit并回车打开注册表编辑器，通过修改注册表进行关闭445端口。\n3.在注册表修编辑器中进入路径：\nHTTP\\HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\NetBT\\Parameters\n4.建立一个DWORD项，名称为SMBDeviceEnabled,将这个新创建的DWORD值的数值数据设置为0。445端口通常用于SMB（ServerMessageBlock）协议，其协议主要用于实现文件共享等功能，这里采用禁用SMB设备来关闭445端口。\n5.做完以上步骤再进入"服务"管理器进行445端口相关的服务关闭，右键计算机点击管理。\n点击"服务和应用程序"，然后双击"服务"进入服务窗口。\n下拉菜单栏找到名为"Server"、"Workstation"、"TCP/IPNetBIOSHelper"的服务，右键点击该服务选择"禁用"选项，之后双击进入该服务，在"常规"选项中，将"启动类型"改为禁止。\n8.重启电脑，点击"菜单"，在"运行"中打开输入cmd打开"命令提示符"，输入netstat-an指令进行查看端口，这里可以看到445端口已关闭。\n随后做了\n防范措施\n本次端口开放报警事件违反了《电力监控系统安全防护规定》（国家发改委令第27号，2025年施行）第11条：生产控制区与管理信息区、安全接入区之间边界，禁止任何穿越的通用网络服务，必须采取边界防护措施。第13条：生产控制区禁止采用高风险通用网络服务，应对外设与端口接入行为严格管控。已对站内运维人员做了相关网络安全知识教育。\n事件发生后，针对站内监测对象做了以下安全措施：1.对所有系统进行全面扫描，对所有已知漏洞进行了补丁更新，确保系统安全性，告警主机已无中高端口处于开放状态；2.配置防火墙，限制445等中高端口的访问；3.对所有员工进行网络安全意识培训，提高对钓鱼邮件、恶意软件等威胁的认识。\n对有关责任人的处理\n1.对直接责任人张三给予通报批评、诫勉谈话、经济处罚，离岗参加网络安全专项培训，考核合格后方可返岗。\n2.对当班班组长/专责李四给予通报批评、绩效扣分处理。\n3.对负有管理责任的部门负责人王五进行提醒约谈，督促切实履行管理职责。\n附件\n1.系统告警记录\n2.事件现场取证照片与整改完成照片\n加固前，445端口处于开放状态：\n加固后，445端口未监听：\n所有主机整改完成照片\n110kVXX站内有两台主机类资产，另一台为五防主机，相关加固佐证如下，已无中高危端口开放。\n4.事件通报与处罚文件\n5.网络安全培训材料、签到表与考核记录\n4.相关管理制度文件、网络安全保密协议复印件"
  }
}
"""