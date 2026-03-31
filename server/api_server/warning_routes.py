from __future__ import annotations
from fastapi import APIRouter, Body
from fastapi.responses import FileResponse

from utils import build_logger
from server.warning_analysis.gen_notice import generate_doc_from_data
from server.warning_analysis.report_analyze import warning_analyze, save_warning_report, delete_warning_report

logger = build_logger()

warning_router = APIRouter(prefix="/warning", tags=["告警处置报告研判"])

warning_router.post(
    "/analyze",
    summary="对告警处置报告进行研判",
)(warning_analyze)


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
                "receive": "湖北宜昌地调",  # 接收单位
                "editor": "张三岁",  # 编制人
                "auditor": "李四岁",  # 审核人
                "warning_time": "2026年02月03日",  # 告警接收时间
                "warning_unit": "宜昌地调网安平台东流溪二级水电站",  # 告警产生单位
                "monitor_device": "监测装置",  # 设备名称
                "warning_level": "紧急",  # 告警级别名称
                "latest_time": "2026-02-03 14:28:36",  # 告警最新发生时间
                "device_ip": "192.168.100.23",  # 告警设备IP
                "content": "电力监控系统终端存在未授权访问风险",  # 告警核心内容
                "reason_analysis": "现场运维人员安全意识不足，未严格执行《电力监控系统网络安全管理规定》，终端配置未做安全加固",
                # 原因分析
                "disposal_suggest": "1. 立即关闭默认高危端口3389；\n2. 修改管理员为强密码（8位以上字母+数字+特殊符号）；\n3. 开启终端日志审计并配置远程上报；\n4. "
                                    "对运维人员开展网络安全专项培训",
                # 处置建议
                "deadline": "2026年02月20日",  # 整改截止日期
                "contact_tel": "027-8866XXXX",  # 省调联系电话
                "cur_date": "2026年02月01日"  # 通知单发布日期
            }
        )
):
    return generate_doc_from_data(data)


warning_router.post(
    "/save_warning_report",
    summary="保存告警处置报告",
)(save_warning_report)


warning_router.post(
    "/delete_warning_report",
    summary="删除告警处置报告",
)(delete_warning_report)
