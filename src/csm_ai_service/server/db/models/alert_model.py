"""
历史告警处置报告知识库模型
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean

from csm_ai_service.server.db.base import Base
from csm_ai_service.server.db.models.base import get_shanghai_time


class AlertReportModel(Base):
    """
    历史告警处置报告 - 存储告警处置全流程信息
    status: "cache" 缓存状态（首次插入），"saved" 已保存状态（明确确认保存）
    """
    __tablename__ = "alert_report"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="报告唯一ID")
    report_title = Column(String(255), default="", comment="报告标题")
    alert_content = Column(Text, default="", comment="告警内容")
    meta_info = Column(Text, default="", comment="告警元信息")
    file_name = Column(String(255), default="", unique=True, comment="报告文件名称（唯一键）")
    full_text = Column(Text, default="", comment="文档段落文本（不含表格）")
    table_data_text = Column(Text, default="", comment="文档表格数据文本")
    status = Column(String(20), default="cache", nullable=False, comment="状态：cache=缓存, saved=已保存")

    # 全文检索索引字段：对告警内容做jieba分词后的结果
    keywords_index = Column(Text, default="", comment="jieba分词索引（对告警内容建立，空格分隔）")

    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(DateTime, default=get_shanghai_time(), onupdate=get_shanghai_time(), comment="更新时间")

    def __repr__(self):
        return f"<AlertReport(id={self.id}, report_title='{self.report_title}', status='{self.status}')>"


class AlertRuleModel(Base):
    """
    告警处置规则库 - 存储告警处置规则
    """
    __tablename__ = "alert_rule"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="规则唯一ID")
    rule_code = Column(String(64), default="", unique=True, comment="规则编号（唯一键）")
    name = Column(String(255), nullable=False, comment="规则名称")
    description = Column(Text, default="", comment="规则详细描述")

    # 全文检索索引字段：对规则名称+描述做jieba分词后的结果
    keywords_index = Column(Text, default="", comment="jieba分词索引（对规则内容建立，空格分隔）")

    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(DateTime, default=get_shanghai_time(), onupdate=get_shanghai_time(), comment="更新时间")

    def __repr__(self):
        return f"<AlertRule(id={self.id}, name='{self.name}')>"
