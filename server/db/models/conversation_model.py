from sqlalchemy import JSON, Column, DateTime, Integer, String, func

from server.db.base import Base


class ConversationModel(Base):
    """
    记录对话框
    """

    __tablename__ = "conversation"
    id = Column(String(32), primary_key=True, comment="聊天记录ID")
    conversation_id = Column(String(32), default=None, index=True, comment="对话框ID")
    chat_type = Column(String(50), comment="聊天类型")
    query = Column(String(4096), comment="用户问题")
    response = Column(String(4096), comment="模型回答")
    create_time = Column(DateTime, default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<message(id='{self.id}',,conversation_id='{self.conversation_id}', chat_type='{self.chat_type}', query='{self.query}', response='{self.response}', create_time='{self.create_time}')>"
