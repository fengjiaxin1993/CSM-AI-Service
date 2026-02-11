from __future__ import annotations
from server.chat.similar_mem_chat import similar_mem_chat
from fastapi import APIRouter, Request
from server.chat.chat import chat
from server.chat.kb_chat import kb_chat
from utils import build_logger
from ..chat.mem_chat import mem_chat
from fastapi.responses import FileResponse
from ..warning_analysis.warning_api import warning_analyze

logger = build_logger()

warning_router = APIRouter(prefix="/warning", tags=["告警处置报告研判"])

warning_router.post(
    "/analyze",
    summary="对告警处置报告进行研判",
)(warning_analyze)


@warning_router.post(
    "/generate_notice",
    summary="生成整改通知单",
    response_class=FileResponse)
def generate_rectification_notice_pdf(
        data: dict = Body(
            ...,
            description="整改通知单填充数据，JSON格式，字段与模板占位符一致",
            example={
                "notice_no": "HBEDC20260211001",
                "receive_unit": "宜昌地调",
                "editor": "张三",
                "auditor": "李四",
                "alarm_time": "2026年02月03日",
                "monitor_device": "宜昌地调网安平台东流溪二级水电站",
                "latest_time": "2026-02-03 14:28:36",
                "alarm_ip": "192.168.100.23",
                "alarm_content": "电力监控系统终端存在未授权访问风险",
                "alarm_detail": "1. 终端开放默认端口3389；\n2. 管理员密码为弱密码；\n3. 未开启日志审计功能",
                "reason_analysis": "现场运维人员安全意识不足，未严格执行《电力监控系统网络安全管理规定》",
                "disposal_suggest": "1. 立即关闭默认高危端口3389；\n2. 修改管理员为强密码；\n3. 开启终端日志审计",
                "deadline": "2026年02月20日",
                "contact_tel": "027-8866XXXX",
                "issue_date": "2026年02月11日"
            }
        )
):
    """
    生成电力监控系统网络安全隐患整改通知单PDF接口
    - 请求方式：POST
    - 请求体：JSON格式填充数据
    - 返回：PDF文件流（可直接下载，文件名自动生成为「整改通知单-编号.pdf」）
    """
    # 生成PDF临时文件
    pdf_path = generate_pdf_from_data(data)
    # 自定义下载文件名
    download_name = f"整改通知单-{data['notice_no']}.pdf"
    # 返回PDF文件流，响应完成后自动删除临时文件
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_name,
        background=None  # 自动清理临时文件
    )
