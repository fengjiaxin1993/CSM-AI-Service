from sqlalchemy import Column, String, Text, JSON, DateTime, Integer
from csm_ai_service.server.db.base import Base
from csm_ai_service.server.db.models.base import get_shanghai_time


class AuditRuleModel(Base):
    """
    审计规则模型
    """
    __tablename__ = "audit_rule"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="规则唯一ID")
    name = Column(String(255), nullable=False, comment="规则名称（简短描述）")
    description = Column(Text, default="", comment="规则详细描述（用于提示大模型）")
    chapter_keywords = Column(JSON, default=list, comment="相关章节关键词列表")
    judge_logic = Column(Text, default="", comment="判断逻辑")
    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(DateTime, default=get_shanghai_time(), onupdate=get_shanghai_time(), comment="更新时间")

    def __repr__(self):
        return (f"<AuditRule(id='{self.id}', name='{self.name}', "
                f"chapter_keywords={self.chapter_keywords}, judge_logic='{self.judge_logic[:30]}...')>")
