from fastapi import APIRouter

from csm_ai_service.server.csm_analyze.protection_pdf_extract.extract_api import upload_extract_safe_table, extract_dbcp_info, \
    upload_extract_safe_split_table, predict_security_type_list, SecurityPredictRequest

pdf_extract_router = APIRouter(prefix="/parse_pdf", tags=["parse pdf file"])

# 上传文件后，提取安全问题风险分析对应的表格, 保留原始表格样式
pdf_extract_router.post(
    "/extract_safe_table",
    summary="上传文件后，提取安全问题风险分析对应的表格",
)(upload_extract_safe_table)


# 上传等保测评文件后，提取报告时间、测评结论、综合得分
pdf_extract_router.post(
    "/extract_dbcp_info",
    summary="上传等保测评文件后，提取报告时间、测评结论、综合得分",
)(extract_dbcp_info)


# 上传文件后，提取安全问题风险分析表格后，对关联资产列进行split
pdf_extract_router.post(
    "/extract_safe_split_table",
    summary="上传文件后，提取安全问题风险分析表格后，对关联资产列进行split",
)(upload_extract_safe_split_table)


# 批量预测安全类型，基于文本匹配，结果确定性
pdf_extract_router.post(
    "/predict_security_type",
    summary="输入安全问题列表，预测安全类型和置信度（基于文本匹配，结果确定性）",
)(predict_security_type_list)
