from __future__ import annotations
from fastapi import APIRouter, Body
from starlette.responses import FileResponse

from csm_ai_service.server.csm_analyze.warning_analysis.gen_notice import generate_doc_from_data
from csm_ai_service.server.csm_analyze.warning_analysis.report_analyze import mock_save_warning_report, \
    mock_delete_warning_report, warning_report_analyze
from csm_ai_service.utils import build_logger

logger = build_logger()

warning_router = APIRouter(prefix="/warning", tags=["告警处置报告研判【同步方法】"])

warning_router.post(
    "/analyze",
    summary="对告警处置报告研判",
)(warning_report_analyze)






@warning_router.post(
    "/generate_notice_doc",
    summary="生成整改通知单-doc",
    response_class=FileResponse)
def generate_rectification_notice_doc(
        data: dict = Body(
            ...,
            description="整改通知单填充数据，JSON格式，字段与模板占位符一致",
            example={
                "notice_no": "WLAQ2026021001",  # 通知单编号
                "receive": "宜昌地调",  # 接收单位
                "editor": "张威",  # 编制人
                "auditor": "刘瑞林",  # 审核人
                "warning_time": "2026年02月03日",  # 告警接收时间
                "warning_unit": "宜昌地调网安平台东流溪二级水电站",  # 告警产生单位
                "monitor_device": "监测装置",  # 设备名称
                "warning_level": "紧急",  # 告警级别名称
                "latest_time": "2026-02-03 14:28:36",  # 告警最新发生时间
                "device_ip": "192.168.100.23",  # 告警设备IP
                "content": "综自后台主机（198.120.0.181）服务器开放了SMB（445）服务端口",  # 告警核心内容
                # 处置建议
                "rectification_requirements": "1.请于2026年6月11日前完成消缺，三日内填写整改情况并盖章，将此整改通知单和已盖章的附件1扫描后，一并发送至省调（sdwlaq@hb.sgcc.com.cn）。\n2.若未能按时完成整改并反馈告警处置报告，省调将进行相关考核。\n3.省调联系电话027-88566839。",  # 整改截止日期
                "cur_date": "2026年02月01日"  # 通知单发布日期
            }
        )
):
    return generate_doc_from_data(data)


warning_router.post(
    "/save_warning_report",
    summary="保存告警处置报告",
)(mock_save_warning_report)


warning_router.post(
    "/delete_warning_report",
    summary="删除告警处置报告",
)(mock_delete_warning_report)
