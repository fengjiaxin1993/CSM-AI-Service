from sqlalchemy import JSON, Column, DateTime, Integer, String, func

from server.db.base import Base


class MessageModel(Base):
    """
    聊天记录模型
    """

    __tablename__ = "message"
    id = Column(String(32), primary_key=True, comment="聊天记录ID（记录问题-回答）")
    conversation_id = Column(String(32), default=None, index=True, comment="对话框ID")
    query = Column(String(4096), comment="用户问题")
    response = Column(String(4096), comment="模型回答")
    create_time = Column(DateTime, default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<message(id='{self.id}',conversation_id='{self.conversation_id}', query='{self.query}', response='{self.response}', create_time='{self.create_time}')>"