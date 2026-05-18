from sqlalchemy import Column, DateTime, Integer, String, func, Boolean

from server.db.base import Base


class ConversationModel(Base):
    """
    会话管理模型
    """

    __tablename__ = "conversation"
    id = Column(String(32), primary_key=True, comment="对话框ID")
    conversation_name = Column(String(255), default="新对话", comment="对话框名称")
    user_id = Column(String(32), index=True, comment="用户ID")
    is_favorite = Column(Integer, default=0, comment="是否收藏")
    create_time = Column(DateTime, default=func.now(), comment="创建时间")
    update_time = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<conversation(id='{self.id}', user_id='{self.user_id}', conversation_name='{self.conversation_name}', is_favorite='{self.is_favorite}', create_time='{self.create_time}')>"
