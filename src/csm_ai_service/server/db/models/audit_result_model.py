"""
审计结果模型 - 存储每个任务中每条审计规则的执行结果
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.dialects.mysql import JSON

from csm_ai_service.server.db.base import Base


class AuditResultModel(Base):
    """
    任务-规则关联表 - 存储每个任务中每条审计规则的执行结果
    """
    __tablename__ = "audit_result"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="关联ID")
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False, index=True, comment="任务ID")
    rule_id = Column(Integer, ForeignKey("audit_rule.id"), nullable=False, index=True, comment="审计规则ID")
    contract_id = Column(Integer, ForeignKey("contract.id"), nullable=False, index=True, comment="合同ID(冗余)")

    # 规则快照
    rule_name = Column(String(256), default="", comment="规则名称")
    rule_description = Column(Text, default="", comment="规则描述")
    rule_judge_logic = Column(Text, default="", comment="判断逻辑")

    # 审计结果
    is_compliant = Column(Boolean, default=False, comment="是否合规: False=不通过, True=通过")
    conclusion = Column(Text, default="", comment="结论描述")
    reasoning = Column(Text, default="", comment="判断理由/解释")
    origin_text = Column(Text, default="", comment="从原文中找出的相关内容")

    # 引用信息
    related_chapters = Column(JSON, default=list, comment="引用的相关章节名")
    related_text = Column(Text, default="", comment="引用的相关原文")
    related_doc_ids = Column(JSON, default=list, comment="引用的相关文档ID")

    def __repr__(self):
        return f"<AuditResult(id={self.id}, task_id={self.task_id}, rule_id={self.rule_id}, is_compliant={self.is_compliant})>"
