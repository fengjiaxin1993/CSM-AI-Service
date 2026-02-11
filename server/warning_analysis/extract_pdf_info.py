import fitz
import re
import json
from typing import Dict, Optional


# {
#   "报告标题": "·XX地调关于X月X日XX变的告警情况说明",
#   "告警信息": "该告警被XX一平面II区监测装置拦截并上报至地调网络安全监视平台，后上传至省调网络安全监测平台，告警内容为由综自后台1（XXXX）拦截XXXX的XXX端口向XXX的X端口之间存在XX端口访问。",
#   "设备名称": "XXX监测装置",
#   "设备类型": "监测装置",
#   "告警时间": "2025-X-XX:X:X",
#   "告警内容": "由综自后台1（XX）拦截XXXX的XX端口向XXX的XX端口之间存在XX端口访问",
#   "处置过程": "1、在收到省调安防的电力监控系统网络安全隐患整改通知单后，XX地调自动化于x月x日上午联系XX变所属检修单位，告知XX期间无检修计划安排且检修人员安规未考试，计划X日进行现场处置。2、X日上午，检修人员到达现场通过查看综自后台1运行情况发现7号该台电脑存在自动重启现象，且现场后台主机所运行的南瑞继保监控程序至14日都未正常运行。如下图；图1：设备运行情况3、在确定该台主机存在重启后且现场主机业务系统厂家南瑞继保所采用SQLServer2000使用NetBios协议进行通讯，业务系统启动时会自动启用轮询，监控客户端和服务器端的数据收发区域，测试读取和写入功能得过程，通过查看该台主机网卡配置，发现该主机同时存在A/B网段IP（xxx），且均处于在用状态，因此会对该网段全部主机进行随机端口扫描。同时查看该主机探针网络白名单，发现xx不在该白名单内，如图2所示，随即自动化值班人员通过网安平台添加白名单后（图3）告警消除。图2：白名单未添加图3：添加白名单",
#   "原因分析": "(1)经变电检修人员现场检查，根据后台主机监控系统运行时常，判断出杨家湾变电站综自后台主机1于7号出现过自动重启现象，该台主机系统为WindowsXP系统，存在系统老旧、内存较低、长久未更新等因素，长时间运行后存在程序无响应、死机等状况，因此业务系统厂家南瑞继保根据主机监控程序运行情况设置了自动重启机制。(2)该站综自后台业务系统均为南瑞继保公司系统，商用库采用XXXX，由于XXXXX使用XXXX协议进行通讯，因此业务系统启动时会自动启用轮询，监控客户端和服务器端的数据收发区域，测试读取和写入功能（针对该站后台主机所在A/B网段XXXXX进行全网扫描），造成多次由综自后台主机1采用随机端口（XXX）访问综自后台主机2（XXXX）目的端口XXX端口的告警产生。",
#   "整改情况": "已通过地调网安平台添加后台综自主机1B网IP地址白名单。如下图：",
#   "防范措施": "1、强化运维管理。组织学习电力监控系统网络安全相关管理规定，修编完善设备巡视、现场作业指导卡等。2、针对老旧存在漏洞等操作系统进行国产化替代，通过改造，使用安全性更好的国产化操作系统和自主可控硬件平台。"
# } 解析告警处置报告结构化结果


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


class PowerAlarmReportParser:
    """电力行业告警报告PDF解析器（适配指定Word模板）"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        try:
            self.doc = fitz.open(self.pdf_path)
            self.tables = self._get_tables()  # 1.先读取table数据
            self.table_dic = self.extract_alarm_info()  # 2.读取table数据
            self.full_text = self._read_pdf()  # 2.跳过table, 读取全文
            self.structured_data = _init_structured_fields()  # 初始化结构化字段
        finally:
            self.doc.close()

    def _read_pdf(self) -> str:
        """读取PDF全文，越过表格数据"""
        bbox_list = []  # 表格边框坐标
        if self.tables:
            for table in self.tables:
                bbox_list.append(table.bbox)

        full_text = ""
        if self.doc:
            for page_idx in range(self.doc.page_count):
                page = self.doc.load_page(page_idx)
                blocks = page.get_text("dict")['blocks']
                for idx, block in enumerate(blocks):
                    type_int = block['type']
                    if type_int == 0:  # 只保留文本信息
                        lines = block["lines"]
                        for line in lines:
                            spans = line['spans']
                            direction = line["dir"]  # 获取文字方向向量
                            if direction[0] != 1.0 or direction[1] != 0.0:  # 去除倾斜方向的文字
                                continue
                            for span in spans:
                                bbox = span['bbox']
                                if not bbox_in_area(bbox, bbox_list):
                                    full_text += span["text"]

            full_text = clean_text(full_text)
        return full_text.strip()

    def extract_alarm_info(self) -> dict:  # 从table中取出表信息
        dic = {}
        if self.tables:
            pd_table = self.tables[0].to_pandas()
            for col_name in pd_table.columns:
                dic[col_name] = clean_text(pd_table[col_name].tolist()[0])
        return dic

    def _get_tables(self, page=0):
        page = self.doc.load_page(page)
        tables = page.find_tables()
        return tables.tables

    def _extract_section_content(self, section_name: str, next_section_name: Optional[str] = None) -> str:
        """提取指定模块的内容（如处置过程、原因分析）"""
        if not section_name and not next_section_name:  # 都为空
            return ""
        elif not section_name and next_section_name:  # section为空，next_section_name不为空
            pattern = rf"\s*(.+?)\s*{next_section_name}"
        elif section_name and not next_section_name:
            pattern = rf"{section_name}\s*(.+?)$"  # 最后一个模块（防范措施）
        else:
            pattern = rf"{section_name}\s*(.+?)\s*{next_section_name}"

        match = re.search(pattern, self.full_text, re.DOTALL)
        if match:
            content = match.group(1).strip()
            # 符号冗余
            content = re.sub(r"\s+", " ", content)  # 合并空格
            return content
        return ""

    def parse(self) -> Dict:
        """执行完整解析流程"""
        # 1. 提取标题
        self.structured_data["报告标题"] = self._extract_section_content("", "一、告警信息")
        # 2. 提取告警信息
        self.structured_data["告警信息"] = self._extract_section_content("一、告警信息", "二、处置过程")
        # 提取告警表格信息
        self.structured_data["设备名称"] = self.table_dic["设备名称"]
        self.structured_data["设备类型"] = self.table_dic["设备类型"]
        self.structured_data["告警时间"] = self.table_dic["告警时间"]
        self.structured_data["告警内容"] = self.table_dic["告警内容"]
        # 3. 提取处置过程
        self.structured_data["处置过程"] = self._extract_section_content("二、处置过程", "三、原因分析")
        # 4. 提取原因分析
        self.structured_data["原因分析"] = self._extract_section_content("三、原因分析", "四、整改情况")
        # 5. 提取整改情况
        self.structured_data["整改情况"] = self._extract_section_content("四、整改情况", "五、防范措施")
        # 6. 提取防范措施（最后一个模块）
        self.structured_data["防范措施"] = self._extract_section_content("防范措施")
        return self.structured_data


# ---------------------- 测试代码 ----------------------
if __name__ == "__main__":
    # 替换为实际PDF路径（Word模板转换后的PDF）
    PDF_PATH = "./2.7-告警分析报告模板.pdf"
    parser = PowerAlarmReportParser(PDF_PATH)
    result = parser.parse()

    # 打印结构化结果（JSON格式，便于后续RAG检索/大模型研判）
    print("=== 电力告警报告结构化解析结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
