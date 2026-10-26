"""
预警报告审计任务模型 - 存储预警报告审计任务的完整生命周期
每个任务对应一个预警报告文件，经历 PDF解析 -> 审计 两个阶段
"""
from sqlalchemy import Column, String, Text, DateTime
from csm_ai_service.server.db.base import Base
from csm_ai_service.server.db.models.base import get_shanghai_time


class AlertReportTaskModel(Base):
    """
    预警报告审计任务表 - 每个任务对应一个预警报告文件
    状态流转: pending -> pdf_processing -> pdf_done -> audit_processing -> completed/failed
    """
    __tablename__ = "alert_report_task"

    task_id = Column(String(64), primary_key=True, comment="任务唯一ID")

    # 文件信息
    file_id = Column(String(64), nullable=False, comment="告警处置报告文件ID")
    file_name = Column(String(255), nullable=False, comment="告警处置报告文件名")
    file_path = Column(String(512), default="", comment="报告文件存储路径")
    content_hash = Column(String(64), default="", index=True, comment="内容SHA-256哈希")

    # 任务状态: pending / pdf_processing / pdf_done / audit_processing / completed / failed
    status = Column(String(30), default="pending", comment="任务状态")

    # 子阶段状态
    pdf_status = Column(String(20), default="pending", comment="PDF解析阶段状态: pending/processing/done/failed")
    audit_status = Column(String(20), default="pending", comment="审计阶段状态: pending/processing/done/failed")

    # 审计结果
    result_json = Column(Text, default="", comment="审计结果JSON")

    # 错误信息
    error_message = Column(Text, default="", comment="错误信息")

    # 时间记录
    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(DateTime, default=get_shanghai_time(), onupdate=get_shanghai_time(), comment="更新时间")

    pdf_start_time = Column(DateTime, default=None, comment="PDF解析开始时间")
    pdf_end_time = Column(DateTime, default=None, comment="PDF解析结束时间")
    audit_start_time = Column(DateTime, default=None, comment="审计开始时间")
    audit_end_time = Column(DateTime, default=None, comment="审计结束时间")

    def __repr__(self):
        return f"<AlertReportTask(task_id={self.task_id}, file_name='{self.file_name}', status='{self.status}')>"
