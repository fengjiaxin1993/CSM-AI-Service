"""
任务模型 - 存储异步任务的完整生命周期
每个任务对应一个合同，经历 OCR识别 -> 审计 两个阶段
数据库不存储路径信息，路径通过 contract_id 和 file_name 动态拼接。
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Boolean
from csm_ai_service.server.db.base import Base
from csm_ai_service.server.db.models.base import get_shanghai_time


class TaskModel(Base):
    """
    任务表 - 每个任务对应一个合同文件
    状态流转: pending -> ocr_processing -> ocr_done -> audit_processing -> completed/failed
    """
    __tablename__ = "task"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="任务唯一ID")
    contract_id = Column(Integer, ForeignKey("contract.id"), nullable=False, index=True, comment="关联合同ID")

    # 任务状态: pending / ocr_processing / ocr_done / audit_processing / completed / failed
    status = Column(String(30), default="pending", comment="任务状态")

    # 子阶段状态（冗余，方便快速查询）
    ocr_status = Column(String(20), default="pending", comment="OCR阶段状态: pending/processing/done/failed")
    audit_status = Column(String(20), default="pending", comment="审计阶段状态: pending/processing/done/failed")

    # 阶段结果
    # OCR 识别结果存储在文件系统 data/cache/{contract_id}/，通过 contract_id 查找
    audit_report = Column(Text, default="", comment="审计汇总报告")

    # 错误信息
    error_message = Column(Text, default="", comment="错误信息")

    # 时间记录
    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(DateTime, default=get_shanghai_time(), onupdate=get_shanghai_time(), comment="更新时间")

    ocr_start_time = Column(DateTime, default=None, comment="OCR开始时间")
    ocr_end_time = Column(DateTime, default=None, comment="OCR结束时间")
    audit_start_time = Column(DateTime, default=None, comment="审计开始时间")
    audit_end_time = Column(DateTime, default=None, comment="审计结束时间")

    def __repr__(self):
        return f"<Task(id={self.id}, contract_id={self.contract_id}, status='{self.status}')>"