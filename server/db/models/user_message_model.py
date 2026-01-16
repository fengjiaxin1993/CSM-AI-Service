from sqlalchemy import JSON, Column, DateTime, Integer, String, func

from server.db.base import Base


class UserMessageModel(Base):
    """
    聊天记录模型,和Faiss关联
    """

    __tablename__ = "user_message"
    id = Column(String(32), primary_key=True, comment="聊天记录ID")
    user_id = Column(String(32), comment="用户ID")
    chat_type = Column(String(50), comment="聊天类型")
    query = Column(String(4096), comment="用户问题")
    response = Column(String(4096), comment="模型回答")
    create_time = Column(DateTime, default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<message(id='{self.id}', user_id='{self.user_id}', chat_type='{self.chat_type}', query='{self.query}', response='{self.response}', create_time='{self.create_time}')>"
