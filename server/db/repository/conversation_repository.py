import uuid
from typing import List, Optional
from sqlalchemy import desc
from server.db.models.conversation_model import ConversationModel
from server.db.models.message_model import MessageModel
from server.db.session import with_session


@with_session
def create_conversation(session, user_id: str, conversation_id: str = None, conversation_name: str = None) -> str:
    """
    创建新会话
    """
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    m = ConversationModel(
        id=conversation_id,
        user_id=user_id,
        conversation_name=conversation_name
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def get_conversation_by_id(session, conversation_id: str) -> Optional[ConversationModel]:
    """
    根据ID获取会话
    """
    return session.query(ConversationModel).filter_by(id=conversation_id).first()


@with_session
def get_conversations_by_user(session, user_id: str, limit: int = 20, offset: int = 0) -> List[dict]:
    """
    获取用户的会话列表，按时间倒序
    """
    conversations = session.query(ConversationModel).filter_by(user_id=user_id) \
        .order_by(desc(ConversationModel.update_time)) \
        .offset(offset).limit(limit).all()

    # 在 session 内将模型转换为字典，避免后续访问时出现懒加载错误
    data = []
    for c in conversations:
        data.append({
            "id": c.id,
            "user_id": c.user_id,
            "conversation_name": c.conversation_name,
            "is_favorite": c.is_favorite,
            "create_time": c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else None,
            "update_time": c.update_time.strftime("%Y-%m-%d %H:%M:%S") if c.update_time else None,
        })
    return data


@with_session
def update_conversation_name(session, conversation_id: str, conversation_name: str) -> bool:
    """
    更新会话名称
    """
    m = get_conversation_by_id(conversation_id)
    if m is not None:
        m.conversation_name = conversation_name
        session.add(m)
        session.commit()
        return True
    return False





@with_session
def toggle_conversation_favorite(session, conversation_id: str, is_favorite: int) -> bool:
    """
    切换会话收藏状态
    """
    m = get_conversation_by_id(conversation_id)
    if m is not None:
        m.is_favorite = is_favorite
        session.add(m)
        session.commit()
        return True
    return False


@with_session
def delete_conversation(session, conversation_id: str) -> bool:
    """
    删除会话及其关联的对话记录
    """
    # 删除关联的对话记录
    session.query(MessageModel).filter_by(conversation_id=conversation_id).delete()
    # 删除会话
    result = session.query(ConversationModel).filter_by(id=conversation_id).delete()
    session.commit()
    return result > 0


@with_session
def conversation_exists(session, conversation_id: str) -> bool:
    """
    检查会话是否存在
    """
    return session.query(ConversationModel).filter_by(id=conversation_id).first() is not None
