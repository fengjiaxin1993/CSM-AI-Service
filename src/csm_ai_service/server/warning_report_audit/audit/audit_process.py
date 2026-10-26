import os
import json
import hashlib
from typing import Dict, List

from fastapi import UploadFile, File
from csm_ai_service.server.utils import BaseResponse
from csm_ai_service.server.warning_report_audit.audit.extract_tools import extract_json_from_markdown, \
    init_report_json_data
from csm_ai_service.server.warning_report_audit.audit.report_judge_tool import init_analyze_result_json_data, \
    judge_report_by_llm
from csm_ai_service.server.warning_report_audit.tools.locate_tools import find_text_positions_in_blocks
from csm_ai_service.server.warning_report_audit.tools.pdf_parser_tools import PdfParseResult, \
    pdf_to_markdown, TextBlock, parse_text_pdf
from csm_ai_service.server.warning_report_audit.audit.risk_judge_tool import is_high_risk_alert
from csm_ai_service.settings import Settings
from csm_ai_service.utils import build_logger

from csm_ai_service.server.db.repository import search_alert_reports, list_alert_rules, add_alert_report, \
    get_alert_report_by_file_id, gen_file_id, update_alert_report

# 知识库插入、搜索
logger = build_logger()


# 组装 prompt
def construct_rag_prompt(alarm_desc: str, top_k: int = 2):
    docs = search_alert_reports(query=alarm_desc, top_k=top_k)
    """电力行业RAG双层检索，返回同类告警参考"""
    if not docs:
        return "未检索到同类电力告警处置报告"

    # 整理电力专属参考格式
    final_retrieve = ""
    for idx, doc in enumerate(docs):
        meta_info = doc.get("meta_info")
        final_retrieve += f"""
    第{idx+1}条：
    "告警内容"：{meta_info.get("告警内容")}
    "原因分析": {meta_info.get("原因分析")}
    "处置过程": {meta_info.get("处置过程")}
    -----------------------------------
    """
    return final_retrieve



def extract_json_data(result:PdfParseResult) -> Dict:
    markdown = result.markdown
    result_dic = extract_json_from_markdown(markdown)
    return result_dic


# 计算文件内容SHA-256哈希（用于同名不同内容的内容指纹）
def compute_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()


# 获取告警处置报告 json结构化， 从数据库中查找
def get_warning_report_json_by_filepath(
    file_path: str,
    file_name: str = "",
    content_hash: str = "",
) -> BaseResponse:
    """获取报告结构化json：先查库，命中且已抽取则直接返回；未抽取（extracted=False）则重新走大模型抽取并回写。"""

    if not content_hash and file_path and os.path.exists(file_path):
        with open(file_path, "rb") as f:
            content_hash = compute_file_hash(f.read())
    file_id = gen_file_id(file_name) if file_name else ""
    existing = get_alert_report_by_file_id(file_id=file_id) if file_id else None
    if existing is not None:
        # 同名同内容且已通过大模型抽取：直接采用
        if existing.get("extracted") and content_hash and existing.get("content_hash") == content_hash:
            return BaseResponse(data=existing.get("meta_info", init_report_json_data()))
        if existing.get("extracted") and not content_hash:
            return BaseResponse(data=existing.get("meta_info", init_report_json_data()))

    # 数据库中没有 / 未抽取 / 内容已变化：解析文件并抽取
    try:
        markdown_content = existing.get("markdown", "") if existing else ""
        if not markdown_content or existing.get("content_hash") != content_hash:
            markdown_content = pdf_to_markdown(file_path)
        result = extract_json_from_markdown(markdown_content)
    except Exception as e:
        # 已有缓存的结构化数据时降级返回，否则报错
        if existing is not None and existing.get("meta_info"):
            logger.warning(f"抽取{file_name}失败，返回已有数据: {e}")
            return BaseResponse(data=existing.get("meta_info", init_report_json_data()))
        return BaseResponse(code=202, msg=f"解析{file_name}失败，报错信息{e}", data={})

    # 抽取成功后落库（status=cache），同名同内容直接采用，同名不同内容覆盖
    try:
        add_alert_report(
            report_title=result["报告标题"],
            file_name=file_name,
            alert_content=result["告警内容"],
            meta_info=result,
            markdown=markdown_content,
            status=(existing or {}).get("status") or "cache",
            content_hash=content_hash,
            file_id=file_id,
            file_path=file_path,
            extracted=True,
        )
    except Exception as e:
        logger.warning(f"缓存报告到数据库失败（不影响返回结果）: {e}")
    return BaseResponse(data=result)


# 保存告警处置报告到磁盘：以文件名为唯一主键，重名时同内容直接采用、不同内容直接覆盖
def save_to_warning_report_file(file: UploadFile):
    file_name = os.path.basename(file.filename or "")
    if not file_name:
        raise ValueError("文件名为空")
    file_content = file.file.read()  # 读取上传文件的内容
    content_hash = compute_file_hash(file_content)
    os.makedirs(Settings.basic_settings.WARNING_REPORT_DIR, exist_ok=True)
    file_path = os.path.join(Settings.basic_settings.WARNING_REPORT_DIR, file_name)
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            old_content_hash = compute_file_hash(f.read())
        if old_content_hash != content_hash:
            # 同名不同内容：直接覆盖
            logger.info(f"检测到同名不同内容文件{file_name}，已覆盖")
            with open(file_path, "wb") as f:
                f.write(file_content)
        # 同名同内容：直接采用，无需写入
    else:
        with open(file_path, "wb") as f:
            f.write(file_content)
    return str(file_path), content_hash



# 获取研判报告
def get_alarm_report_info(file: UploadFile = File(..., description="上传文件")) -> BaseResponse:
    # 每次都更新缓存
    new_file_path, content_hash = save_to_warning_report_file(file)
    return get_warning_report_json_by_filepath(
        new_file_path, file_name=file.filename, content_hash=content_hash
    )


def get_rules_desc(limit: int = 5):
    rules = list_alert_rules(limit=limit, offset=0)
    results = []
    for idx,rule in enumerate(rules):
        rule_str = f"{idx+1}. {rule.get('name', '')}: {rule.get('description', '')}"
        results.append(rule_str)
    return "\n".join(results)


# 一次性返回研判结果()
def warning_analyze_process(file: UploadFile = File(..., description="上传文件")) -> BaseResponse:
    # 【step1】 获取告警处置报告信息
    new_file_path, content_hash = save_to_warning_report_file(file)
    pdf_result = parse_text_pdf(new_file_path)
    text_blocks = pdf_result.text_blocks

    report_response = get_warning_report_json_by_filepath(
        new_file_path, file_name=file.filename, content_hash=content_hash
    )
    logger.info(f"【step1】 获取告警处置报告信息{file.filename}")
    if report_response.code != 200:
        data = init_analyze_result_json_data()
        data["audit_result"] = "需人工复核"
        data["conclusion"] = f"解析{file.filename}失败"
        return BaseResponse(code=202, msg=report_response.msg, data=data)
    report_data = report_response.data

    # 【step2】 判断是否为高危告警
    alert_content = report_data.get("告警内容", "")
    is_high_risk = is_high_risk_alert(alert_content)
    risk_level = "高危告警" if is_high_risk else "普通告警"
    logger.info(f"【step2】 告警类型判定：{risk_level}，告警内容片段：{alert_content[:100]}")

    # 【step3】 获取规则库
    rules_desc = get_rules_desc(limit=5)
    logger.info("【step3】 获取规则库")

    # 【step4】 获取历史数据信息
    rag_retrieve_info = construct_rag_prompt(alarm_desc=report_data["告警内容"],
                                             top_k=2)
    logger.info("【step4】获取历史数据信息")


    # 【step5】 组装提示词（根据高危/普通选择不同模板）
    report_info = json.dumps(report_data, ensure_ascii=False, indent=2)
    try:
        analyze_dic = judge_report_by_llm(is_high_risk=is_high_risk,rules_info=rules_desc,
                                      retrieved_info=rag_retrieve_info, report_info=report_info )
        analyze_dic = find_field_positions(analyze_dic, text_blocks)
        return BaseResponse(data=analyze_dic)
    except Exception as e:
        data = init_analyze_result_json_data()
        data = find_field_positions(data, text_blocks)
        data["audit_result"] = "需人工复核"
        return BaseResponse(code=203, msg=f"大模型分析{file.filename}失败，请人工查看，报错信息{e}", data=data)


# 保存处置报告
def save_warning_report(
        file: UploadFile = File(..., description="上传文件"),
) -> BaseResponse:
    # 先落盘并计算内容哈希（文件流只能读一次，故不经过get_alarm_report_info重复读取）
    file_path, content_hash = save_to_warning_report_file(file)
    report_response = get_warning_report_json_by_filepath(
        file_path, file_name=str(file.filename), content_hash=content_hash
    )
    if report_response.code != 200:
        return BaseResponse(code=report_response.code, msg=f"解析报告失败，无法保存: {report_response.msg}")
    report_data = report_response.data
    try:
        # 以文件名为唯一主键查询是否已在数据库
        existing = get_alert_report_by_file_id(file_id=gen_file_id(file.filename))
        if existing is None:
            # 不在数据库中，新增，状态为saved
            file_id = add_alert_report(
                report_title=report_data["报告标题"],
                file_name=file.filename,
                alert_content=report_data["告警内容"],
                meta_info=report_data,
                status="saved",
                content_hash=content_hash,
                file_path=file_path,
                extracted=True,
            )
            return BaseResponse(code=200, msg=f"新增保存成功,file_id={file_id}")
        else:
            if existing.get("status") == "cache":
                # 缓存状态 → 确认保存（cache → saved），同时更新数据
                update_alert_report(
                    file_id=existing["file_id"],
                    report_title=report_data["报告标题"],
                    alert_content=report_data["告警内容"],
                    meta_info=report_data,
                    markdown=existing.get("markdown", ""),
                    status="saved",
                    content_hash=content_hash,
                    file_path=file_path,
                    extracted=True,
                )
                return BaseResponse(code=200, msg=f"缓存报告已确认保存,file_id={existing['file_id']}")
            else:
                # 已经是saved状态，更新内容
                update_alert_report(
                    file_id=existing["file_id"],
                    report_title=report_data["报告标题"],
                    alert_content=report_data["告警内容"],
                    meta_info=report_data,
                    content_hash=content_hash,
                    file_path=file_path,
                    extracted=True,
                )
                return BaseResponse(code=200, msg=f"报告已更新,file_id={existing['file_id']}")
    except Exception as e:
        logger.error(f"保存告警报告到知识库失败: {str(e)}")
        return BaseResponse(code=500, msg=f"保存失败: {str(e)}")



def find_field_positions(json_data: Dict, text_blocks:List[TextBlock]) -> Dict:
    """
    根据json_data，找到原文对应的字段和坐标
    json_data 字典如下
        {
            "audit_result": "需人工复核",
            "audit_details": "",
            "conclusion": "",
            "problem_list": [
                {
                    "text": "",
                    "cause": "",
                    "suggest": ""
                }
            ]
        }
    输出如下
        {
            "audit_result": "需人工复核",
            "audit_details": "",
            "conclusion": "",
            "problem_list": [
                {
                    "text": "告警内容",
                    "cause": "",
                    "suggest": ""
                    "field_positions": [
                        {
                            "block_content": "告警内容",
                            "block_bbox": [120.6,410.4,482.04,425.16],
                            "page_num": 0
                        }
                    ]
                }
            ]
        }

    """
    problem_list = json_data.get("problem_list", [])
    for problem in problem_list:
        problem["field_positions"] = []
        origin_text = problem.get("text", "")
        match_info_list = find_text_positions_in_blocks(origin_text, text_blocks)

        for match_info_dic in match_info_list:
            problem["field_positions"].append({
                "block_content": match_info_dic.get("block_content"),
                "block_bbox": match_info_dic.get("block_bbox"),
                "page_num": match_info_dic.get("page_num")
            })
    return json_data

if __name__ == "__main__":
    json_data = {
        "audit_result": "驳回",
        "audit_details": "经研判，告警属实：非实时监测装置与省调平台通信中断、纵向加密存在0.0.0.0默认路由，均属真实网络安全隐患；默认路由可能扩大访问范围，但报告称业务正常，未见实际外联或病毒证据。按四不放过及高危告警审核要求，处置过程基本完整，但根因、责任处理、教育培训、佐证材料和防复发整改闭环不足，不能直接通过。",
        "conclusion": "经审核，本次告警属实，但报告未满足四不放过要求，予以驳回。请补充：查清非实时监测证书异常和纵向加密0.0.0.0默认路由产生根因；认定并处理责任单位、责任人员；开展人员教育培训并留痕；附证书重导、路由删除前后配置、设备在线、省调核实、现场处置等佐证；完善同类隐患排查、配置基线、变更审批和监控等防复发整改措施，并说明8月28日至31日处置延迟原因。修改后重新报送。",
        "problem_list": [
          {
            "text": "原因分析：1、监测装置：需要省调网安平台重新导入太山寺变非实时监测装置资产证书。2、纵向加密：纵向加密设备运行不稳定，远程调阅路由配置导致设备死机。",
            "cause": "仅描述处置需求和直接诱因，未查清证书异常根因、默认路由来源、设备死机与默认路由之间的完整事故链。",
            "suggest": "深化根因分析，说明证书过期、不匹配或同步失败等原因，查清0.0.0.0默认路由配置来源及责任环节。",
          },
          {
            "text": "联系省调自动化值班发现太山寺变省网业务正常。",
            "cause": "仅凭业务正常不能排除默认路由对网络边界和访问控制的影响，未评估风险等级和影响范围。",
            "suggest": "补充风险等级、影响范围评估，说明是否可能被利用、是否涉及横向访问或外联，并提供业务与安防双重确认记录。"
          }
        ]
      }
    new_file_path = "./test.pdf"
    pdf_result = parse_text_pdf(new_file_path)
    text_blocks = pdf_result.text_blocks
    json_data = find_field_positions(json_data, text_blocks)
    print(json_data)
    res_data = {
        'audit_details': '经研判，告警属实：非实时监测装置与省调平台通信中断、纵向加密存在0.0.0.0默认路由，均属真实网络安全隐患；默认路由可能扩大访问范围，但报告称业务正常，未见实际外联或病毒证据。按四不放过及高危告警审核要求，处置过程基本完整，但根因、责任处理、教育培训、佐证材料和防复发整改闭环不足，不能直接通过。',
        'audit_result': '驳回',
        'conclusion': '经审核，本次告警属实，但报告未满足四不放过要求，予以驳回。请补充：查清非实时监测证书异常和纵向加密0.0.0.0默认路由产生根因；认定并处理责任单位、责任人员；开展人员教育培训并留痕；附证书重导、路由删除前后配置、设备在线、省调核实、现场处置等佐证；完善同类隐患排查、配置基线、变更审批和监控等防复发整改措施，并说明8月28日至31日处置延迟原因。修改后重新报送。',
        'problem_list': [
            {'cause': '仅描述处置需求和直接诱因，未查清证书异常根因、默认路由来源、设备死机与默认路由之间的完整事故链。',
             'field_positions': [{'block_bbox': (90.0, 328.50445556640625, 505.1956787109375, 338.9544677734375),
                                  'block_content': '联系南瑞信通厂家后厂家建议需要省调网安平台重新导入太山寺变非实时监测装置资产证',
                                  'page_num': 0},
                                 {'block_bbox': (111.0, 623.2872924804688, 473.27789306640625, 637.2693481445312),
                                  'block_content': '1、监测装置：需要省调网安平台重新导入太山寺变非实时监测装置资产证书。',
                                  'page_num': 0},
                                 {'block_bbox': (111.0, 638.8873291015625, 462.718505859375, 652.869384765625),
                                  'block_content': '2、纵向加密：纵向加密设备运行不稳定，远程调阅路由配置导致设备死机。',
                                  'page_num': 0}],
             'suggest': '深化根因分析，说明证书过期、不匹配或同步失败等原因，查清0.0.0.0默认路由配置来源及责任环节。',
             'text': '原因分析：1、监测装置：需要省调网安平台重新导入太山寺变非实时监测装置资产证书。2、纵向加密：纵向加密设备运行不稳定，远程调阅路由配置导致设备死机。'},
            {'cause': '仅凭业务正常不能排除默认路由对网络边界和访问控制的影响，未评估风险等级和影响范围。',
             'field_positions': [{'block_bbox': (90.0, 451.6872863769531, 481.32073974609375, 465.6694030761719),
                                  'block_content': '加密（科东PSTunnel-2000）离线。联系省调自动化值班发现太山寺变省网业务正常。',
                                  'page_num': 0}],
             'suggest': '补充风险等级、影响范围评估，说明是否可能被利用、是否涉及横向访问或外联，并提供业务与安防双重确认记录。',
             'text': '联系省调自动化值班发现太山寺变省网业务正常。'}]}

