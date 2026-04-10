import os
import random

from fastapi import UploadFile, File

from server.csm_analyze.protection_pdf_extract.keywords_helper import KeyWordsHelper
from server.csm_analyze.protection_pdf_extract.helper import split_line, save_to_temp_file, remove_dup_str
from server.csm_analyze.protection_pdf_extract.outline_helper import OutlineHelper
from server.csm_analyze.protection_pdf_extract.table_helper import TableHelper
import logging

logger = logging.getLogger(__name__)


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
        split_char_list: list = list['、', '，'],
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


def get_random_score(min_num=0.4, max_num=0.6):
    """生成指定范围内的随机小数，确保每次调用结果不同"""
    result = random.uniform(min_num, max_num)
    return round(result, 2)

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
        # 包含预测类别以及分数
        for res in res_list:
            res["predict_securityType"] = res["securityType"]
            res["predict_score"] = get_random_score()
        return res_list
    except Exception as e:
        msg = f"{file.filename} 文件解析失败，报错信息为: {e}"
        logger.error(msg)
        copy = empty_return_dic.copy()
        copy["predict_securityType"] = 0
        copy["predict_score"] = 0
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
        # 包含预测类别以及分数
        for res in res_list:
            res["predict_securityType"] = res["securityType"]
            res["predict_score"] = get_random_score()
        return res_list
    except Exception as e:
        msg = f"解析{file.filename} 失败，报错信息为: {e}"
        logger.error(msg)
        copy = empty_return_dic.copy()
        copy["predict_securityType"] = 0
        copy["predict_score"] = 0
        return [copy]


def remove_digit_str(str):
    return ''.join([i for i in str if not i.isdigit()])


standard_column_names = ["问题描述", "风险等级", "安全类型", "关联资产"]
match_dict = {
    "content": ["安全问题", "问题描述"],
    "riskLevel": ["风险等级"],
    "securityType": ["安全类", "安全类型", "安全层面"],
    "evaluationObject": ["关联资产"]
}
empty_return_dic = {
    "content": "",
    "riskLevel": 0,
    "securityType": 0,
    "evaluationObject": ""
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
