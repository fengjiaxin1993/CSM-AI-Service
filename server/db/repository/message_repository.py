import uuid
from typing import Dict

from server.db.models.message_model import MessageModel
from server.db.session import with_session


# 聊天记录维度

@with_session
def add_message_to_db(
        session,
        conversation_id: str,
        query,
        response="",
        message_id=None,
        metadata: Dict = {},
):
    """
    新增聊天记录
    """
    if not message_id:
        message_id = uuid.uuid4().hex
    m = MessageModel(
        id=message_id,
        query=query,
        response=response,
        conversation_id=conversation_id,
        meta_data=metadata,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def update_response_message(session, message_id, response: str = None):
    """
    更新已有的聊天记录
    """
    m = get_message_by_id(message_id)
    if m is not None:
        if response is not None:
            m.response = response
        session.add(m)
        session.commit()
        return m.id


@with_session
def get_message_by_id(session, message_id) -> MessageModel:
    """
    查询聊天记录
    """
    m = session.query(MessageModel).filter_by(id=message_id).first()
    return m


@with_session
def filter_message(session, conversation_id: str, limit: int = 10, offset: int = 0, asc: bool = False):
    messages = (
        session.query(MessageModel)
        .filter_by(conversation_id=conversation_id)
        .
        # 用户最新的query 也会插入到db，忽略这个message record
        filter(MessageModel.response != "")
        .
        # 返回最近的limit 条记录
        order_by(MessageModel.create_time.asc() if asc else MessageModel.create_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # 倒序返回对话
    data = []
    for m in messages:
        data.append({
            "id": m.id,
            "query": m.query,
            "response": m.response,
            "create_time": m.create_time.strftime("%Y-%m-%d %H:%M:%S") if m.create_time else None,
            "file_id": m.meta_data.get("file_id", ""),
            "file_names": m.meta_data.get("file_names", [])
        })
    return data
