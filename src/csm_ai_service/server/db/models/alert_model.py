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
    以 file_name 为唯一主键：同名且内容哈希相同 -> 视为同一篇报告（直接复用）；
    同名但内容哈希不同 -> 直接覆盖原记录。
    """
    __tablename__ = "alert_report"

    file_id = Column(String(64), primary_key=True, index=True, default="", comment="报告唯一ID（由文件名生成）")
    report_title = Column(String(255), default="", comment="报告标题")
    alert_content = Column(Text, default="", comment="告警内容")
    meta_info = Column(Text, default="", comment="告警元信息")
    file_name = Column(String(255), default="", index=True, comment="报告文件名称")
    file_path = Column(String(512), default="", comment="报告文件存储路径")
    content_hash = Column(String(64), default="", index=True, comment="内容SHA-256哈希（同名时判断内容是否变化）")
    markdown = Column(Text, default="", comment="文档markdown")
    extracted = Column(Boolean, default=False, index=True, comment="是否已通过大模型抽取结构化信息")
    status = Column(String(20), default="cache", nullable=False, comment="状态：cache=缓存, saved=已保存")

    # 全文检索索引字段：对告警内容做jieba分词后的结果
    keywords_index = Column(Text, default="", comment="jieba分词索引（对告警内容建立，空格分隔）")

    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(DateTime, default=get_shanghai_time(), onupdate=get_shanghai_time(), comment="更新时间")

    def __repr__(self):
        return f"<AlertReport(file_id={self.file_id}, report_title='{self.report_title}', status='{self.status}')>"


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
