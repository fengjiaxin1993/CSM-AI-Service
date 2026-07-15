import os
import random
from fastapi import UploadFile, File
from pydantic import BaseModel, Field
from typing import List, Optional

from csm_ai_service.server.csm_analyze.protection_pdf_extract.keywords_helper import KeyWordsHelper
from csm_ai_service.server.csm_analyze.protection_pdf_extract.helper import split_line, save_to_temp_file, remove_dup_str
from csm_ai_service.server.csm_analyze.protection_pdf_extract.outline_helper import OutlineHelper
from csm_ai_service.server.csm_analyze.protection_pdf_extract.table_helper import TableHelper
import logging

logger = logging.getLogger(__name__)


# ====================== 安全类型预测相关 ======================

# 从等保测评样例中提炼的加权关键词规则：
# 每个安全类型包含一组 (关键词, 权重) 对。
# 权重含义：
#   1.0 = 强特征词（出现则几乎确定是该类型，区分度高）
#   0.6 = 中特征词（有较强指示性，但可能与其他类型交叉）
#   0.3 = 弱特征词（辅助判断，区分度低）
#
# 提炼规律：
#   - "通信设备/通信网络" 仅出现在类型1，是强特征；单独的"网络"会与13交叉，所以只给0.3
#   - "边界" 是类型2的核心特征；"安全标记"仅在类型2出现
#   - 类型3覆盖面最广，"数据库/服务器/杀毒/恶意代码"是其强特征
#   - "集中管控/集中运维" 是类型4独有特征
#   - 类型5特征词多为运维管理词汇，"介质/账户管理/办公环境"区分度高
#   - "机房/门禁"是类型6强特征，但与类型12交叉
#   - 类型12的"防盗报警/防雷保安器/烟感/灭火装置"区分度更高
#   - "网络层/网络边界/ARP/入侵检测"是类型13强特征
#   - "主机层/多余服务/多余用户/nobody"是类型14独有
#   - "应用层/并发连接/审计报表"是类型15强特征
#   - 类型16偏管理，"安全顾问"是其独有特征

_security_type_weighted_keywords = {
    1: [("通信设备", 1.0), ("通信网络", 1.0), ("通信安全", 0.6), ("可信验证", 0.3), ("传输过程", 0.3)],
    2: [("区域边界", 1.0), ("边界设备", 0.8), ("安全标记", 0.8), ("边界", 0.6), ("安全防范", 0.6),
        ("接入网络", 0.6), ("终端登录", 0.5), ("可信验证", 0.3), ("传输过程", 0.3), ("存储过程", 0.3),
        ("保密性", 0.3), ("完整性", 0.3)],
    3: [("计算环境", 1.0), ("数据库", 0.8), ("服务器", 0.6), ("杀毒软件", 0.7), ("恶意代码", 0.6),
        ("密码复杂度", 0.7), ("身份鉴别", 0.6), ("三权用户", 0.7), ("漏洞扫描", 0.5),
        ("数据备份", 0.6), ("可信验证", 0.3), ("完整性", 0.4), ("保密性", 0.4),
        ("应用系统", 0.3), ("操作系统", 0.4), ("审计", 0.3), ("SNMP", 0.5)],
    4: [("集中管控", 1.0), ("集中运维", 1.0), ("安全管理中心", 0.8), ("集中管理", 0.6),
        ("管理平台", 0.5), ("系统配置", 0.4), ("审计配置", 0.4)],
    5: [("运维管理", 0.8), ("介质", 0.7), ("账户管理", 0.7), ("办公环境", 0.7),
        ("防恶意代码", 0.5), ("配置保存", 0.5), ("备份策略", 0.5), ("漏洞扫描", 0.3),
        ("补丁", 0.4), ("应急预案", 0.4), ("变更", 0.3), ("操作手册", 0.5)],
    6: [("安全物理环境", 1.0), ("机房出入口", 0.8), ("电子门禁", 0.8), ("消防系统", 0.7),
        ("物理环境", 0.6), ("机房", 0.4), ("温湿度", 0.5), ("供电", 0.5)],
    7: [("管理制度", 0.8), ("安全策略", 0.6), ("规程", 0.5), ("规范", 0.4), ("制度", 0.3)],
    8: [("管理机构", 0.8), ("领导小组", 0.7), ("委员会", 0.6), ("职责", 0.4), ("机构", 0.3)],
    9: [("外部人员", 0.8), ("访问权限", 0.7), ("安全管理人员", 0.7), ("录用", 0.5),
        ("离岗", 0.5), ("培训", 0.4), ("考核", 0.4)],
    10: [("建设管理", 0.8), ("工程实施", 0.7), ("密码技术安全防护", 0.7), ("实施方案", 0.6),
        ("验收", 0.4), ("采购", 0.4), ("设计", 0.3)],
    11: [("生产控制大区", 0.8), ("总体安全", 0.7), ("整体安全", 0.6), ("集中收集", 0.5),
        ("总体", 0.4)],
    12: [("防盗报警", 1.0), ("防雷保安器", 1.0), ("烟感", 0.9), ("灭火装置", 0.8),
        ("双重门禁", 0.8), ("接地防静电", 0.7), ("物理安全", 0.6), ("防雷", 0.5),
        ("机房", 0.3), ("门禁", 0.3)],
    13: [("ARP欺骗", 1.0), ("非法外联", 0.9), ("入侵检测系统", 0.8), ("网络层", 0.8),
        ("网络边界", 0.7), ("第三方审计", 0.7), ("防火墙访问控制", 0.6), ("telnet", 0.6),
        ("本地存储", 0.4), ("网络设备", 0.4), ("网络", 0.3)],
    14: [("主机层", 0.9), ("多余服务", 0.8), ("多余用户", 0.8), ("nobody", 0.9),
        ("操作系统", 0.4), ("审计报表", 0.4), ("主机安全", 0.6)],
    15: [("应用层", 0.9), ("并发连接", 0.8), ("审计报表", 0.5), ("应用系统", 0.4),
        ("登录失败处理", 0.4), ("应用安全", 0.6)],
    16: [("安全顾问", 1.0), ("管理安全", 0.6), ("安全管理", 0.4), ("漏洞扫描", 0.3),
        ("集中管理", 0.3)],
}


class SecurityPredictItem(BaseModel):
    """单项安全类型预测输入"""
    content: str = Field(default="", description="问题描述")
    securityType: int = Field(default=0, description="安全类型编码，0表示未指定")
    seq: int = Field(default=0, description="序号")


class SecurityPredictResult(BaseModel):
    """单项安全类型预测结果"""
    seq: int = Field(default=0, description="序号")
    content: str = Field(default="", description="问题描述")
    predict_securityType: int = Field(default=0, description="预测安全类型编码")
    predict_score: float = Field(default=0, description="置信度，0-1之间")
    securityType: int = Field(default=0, description="原始安全类型编码")


class SecurityPredictRequest(BaseModel):
    """安全类型预测请求"""
    items: List[SecurityPredictItem] = Field(..., description="待预测的安全问题列表")


def _calc_score_for_type(content: str, target_type: int) -> float:
    """
    基于加权关键词匹配计算 content 对某个安全类型的置信度分数。
    逻辑：遍历该类型的所有 (关键词, 权重) 对，
          命中的关键词权重累加，归一化后得到最终分数。
    结果确定性，相同输入始终返回相同结果。
    """
    if not content:
        return 0.0

    content_lower = content.lower()
    weighted_keywords = _security_type_weighted_keywords.get(target_type, [])

    # 计算命中关键词的权重之和
    hit_weight_sum = sum(weight for kw, weight in weighted_keywords if kw.lower() in content_lower)
    # 所有可能的最大权重之和（全部命中）
    max_weight_sum = sum(weight for _, weight in weighted_keywords)

    if max_weight_sum == 0:
        return 0.0

    # 归一化：命中权重 / 最大权重，得到原始分数
    raw_score = hit_weight_sum / max_weight_sum

    # 映射到合理置信度区间：raw_score 0~1 → confidence 0.3~0.95
    # 用线性映射，保证有区分度
    confidence = 0.3 + 0.65 * raw_score

    return round(min(confidence, 0.95), 4)


def _predict_security_type_by_text(content: str) -> tuple:
    """
    根据问题描述文本匹配预测安全类型。
    对每个安全类型计算置信度，取最高分的类型。
    返回 (预测类型编码, 置信度)
    """
    if not content:
        return (0, 0.0)

    best_type = 0
    best_score = 0.0

    for type_code in _security_type_weighted_keywords:
        score = _calc_score_for_type(content, type_code)
        if score > best_score:
            best_score = score
            best_type = type_code

    return (best_type, best_score)


def predict_security_type_list(request: SecurityPredictRequest) -> List[SecurityPredictResult]:
    """
    批量预测安全类型接口。
    - 如果输入已有安全类型(securityType != 0)，预测类型与安全类型一致，置信度仍用统一计算逻辑
    - 如果没有安全类型，根据问题描述文本匹配预测，取最高分类型
    - 结果确定性，相同输入始终返回相同结果
    """
    results = []
    for item in request.items:
        if item.securityType and item.securityType != 0:
            # 已有安全类型，预测类型与之一致，置信度仍用统一计算逻辑
            predict_type = item.securityType
            predict_score = _calc_score_for_type(item.content, predict_type)
            # 已有类型信息加分：至少0.5置信度兜底
            if predict_score < 0.5:
                predict_score = 0.5
        else:
            # 根据问题描述预测
            predict_type, predict_score = _predict_security_type_by_text(item.content)

        results.append(SecurityPredictResult(
            seq=item.seq,
            content=item.content,
            predict_securityType=predict_type,
            predict_score=predict_score,
            securityType=item.securityType,
        ))
    return results


# 抽取表格,返回表格，第一行是表头
def extract_table(
        pdf_path: str,
        start_page: int,
        end_page: int,
        start_chapter: str,
        end_chapter: str) -> list[list[str]]:
    th = TableHelper(pdf_path, start_page, end_page, start_chapter, end_chapter)
    table_list = [th.header_list]
    for line in th.merge_table:
        table_list.append(line)
    return table_list


# 将提取的表格修改后，逐项提出，将关联资产划分
def split_table(
        table_list: list[list[str]],
        split_char_list: list = ['、', '，'],
        key: str = '关联资产') -> list[list[str]]:
    header_list = table_list[0]
    data_list = table_list[1:]
    split_data_list = split_line(header_list, data_list, split_char_list, key)
    res_table_list = [header_list]
    for line in split_data_list:
        res_table_list.append(line)
    return res_table_list


def extract_safe_table(pdf_path: str) -> list[list[str]]:
    oh = OutlineHelper(pdf_path=pdf_path)
    if oh.is_valid():
        return extract_table(pdf_path, oh.start_page, oh.end_page, oh.start_chapter, oh.end_chapter)
    else:
        return empty_table_list

def extract_safe_split_table(pdf_path: str) -> list[list[str]]:
    table_list = extract_safe_table(pdf_path)
    if len(table_list) > 1:
        split_key = '关联资产'
        split_char_list = ['、', '，', ',']
        return split_table(table_list, split_char_list, split_key)
    else:
        return table_list


def upload_extract_safe_table(
        file: UploadFile = File(..., description="上传文件"),
) -> list[dict]:
    """
    将文件保存到临时目录.
    找到安全问题风险分析的表格，解决跨页问题，提取出原始表格。
    """

    try:
        new_file_path = save_to_temp_file(file)
        logger.info(f"【{file.filename}】 save success ，save to 【{new_file_path}】")
        table_list = extract_safe_table(new_file_path)
        os.remove(new_file_path)
        res_list = output_standard(table_list)
        return res_list
    except Exception as e:
        msg = f"{file.filename} 文件解析失败，报错信息为: {e}"
        logger.error(msg)
        copy = empty_return_dic.copy()
        return [copy]


def extract_dbcp_info(
        file: UploadFile = File(..., description="上传文件"),
) -> dict:
    """
    抽取等保测评表中的信息
    """

    try:
        new_file_path = save_to_temp_file(file)
        logger.info(f"【{file.filename}】 save success ，save to 【{new_file_path}】")
        keywords_helper = KeyWordsHelper(new_file_path)
        res = {
            "report_time": keywords_helper.report_time,
            "cpjl": keywords_helper.cpjl,
            "score": keywords_helper.score
        }
        os.remove(new_file_path)
        return res
    except Exception as e:
        msg = f"{file.filename} 文件解析失败，报错信息为: {e}"
        logger.error(msg)
        empty_res = {
            "report_time": "",
            "cpjl": "",
            "score": ""
        }
        return empty_res


def upload_extract_safe_split_table(
        file: UploadFile = File(..., description="上传文件"),
) -> list[dict]:
    """
        将文件保存到临时目录.
        找到安全问题风险分析的表格，解决跨页问题，提取出原始表格后，对表格列（关联资产）进行划分，形成更详细的表格,json格式返回
        """
    try:
        new_file_path = save_to_temp_file(file)
        logger.info(f"【{file.filename}】 save success ，save to 【{new_file_path}】")
        table_list = extract_safe_split_table(new_file_path)
        os.remove(new_file_path)
        res_list = output_standard(table_list)
        return res_list
    except Exception as e:
        msg = f"解析{file.filename} 失败，报错信息为: {e}"
        logger.error(msg)
        copy = empty_return_dic.copy()
        return [copy]


def remove_digit_str(str):
    return ''.join([i for i in str if not i.isdigit()])


standard_column_names = ["问题描述", "风险等级", "安全类型", "关联资产", "关联威胁", "危害分析结果"]
match_dict = {
    "content": ["安全问题", "问题描述"],
    "riskLevel": ["风险等级"],
    "securityType": ["安全类", "安全类型", "安全层面"],
    "evaluationObject": ["关联资产"],
    "relatedThreat": ["关联威胁"],
    "harmAnalysis": ["危害分析结果","危害分析"]
}
empty_return_dic = {
    "content": "",
    "riskLevel": 0,
    "securityType": 0,
    "evaluationObject": "",
    "relatedThreat": "",
    "harmAnalysis": ""
}

empty_table_list = [[]]

# 安全类型 对应的编码
securityType_dic = {
    "安全通信网络": 1,
    "安全区域边界": 2,
    "安全计算环境": 3,
    "安全管理中心": 4,
    "安全运维管理": 5,
    "安全物理环境": 6,
    "安全管理制度": 7,
    "安全管理机构": 8,
    "安全管理人员": 9,
    "安全建设管理": 10,
    "总体安全": 11,
    "物理安全": 12,
    "网络安全": 13,
    "主机安全": 14,
    "应用安全": 15,
    "管理安全": 16,
}

# 编码 -> 安全类型名称的反向字典
securityType_reverse_dic = {v: k for k, v in securityType_dic.items()}

#风险等级 对应的编码
riskType_dic = {
    "高": 1001,
    "中": 1002,
    "低": 1003
}


def get_risk_code(risk_info: str) -> int:
    return riskType_dic.get(risk_info, 0)


def get_securityType_code(security_info: str) -> int:
    security_info = remove_dup_str(security_info)
    return securityType_dic.get(security_info, 0)


def column_match(column_name):
    column_name = remove_digit_str(column_name)
    for k, vlist in match_dict.items():
        if column_name in vlist:
            return k
    return ""


# 一行数据转换成{}格式
def line2dic(header_list: list[str], data_list: list[str]) -> dict:
    dic = {}
    for idx, column in enumerate(header_list):
        standard_name = column_match(column)
        if standard_name != "":
            data = data_list[idx]
            if standard_name == "riskLevel":
                dic[standard_name] = get_risk_code(data)
            elif standard_name == "securityType":
                dic[standard_name] = get_securityType_code(data)
            else:
                dic[standard_name] = data
    return dic


def is_same_dict(dic1, dic2):
    for k, v in dic1.items():
        if k not in dic2:
            return False
        if v != dic2[k]:
            return False
    return True


def output_standard(table_list: list[list[str]]) -> list[dict]:
    if len(table_list) <= 1:
        return [empty_return_dic]
    else:
        res = []
        header_list = table_list[0]
        for data_list in table_list[1:]:
            dic = line2dic(header_list, data_list)
            if is_same_dict(dic, empty_return_dic):
                continue
            else:
                res.append(line2dic(header_list, data_list))
        return res


def name_standard(dic: dict) -> dict:
    res_dic = {}
    for col, v in dic.items():
        standard_col = column_match(col)
        if standard_col != "":
            res_dic[standard_col] = v
    return res_dic


# 判断输出结果是否正确,动态确定snap_tolerance
def output_is_valid(res: list[dict]) -> bool:
    if res == empty_return_dic:
        return False
    if len(res) == 1:
        return False
    for item in res:
        for key, value in item.items():
            if value == '':
                return False
    return True
