import uuid
from typing import Dict, List

from server.db.models.user_message_model import UserMessageModel
from server.db.session import with_session


@with_session
def add_message_to_db(
        session,
        chat_type,
        query,
        response="",
        message_id=None,
        user_id=None
):
    """
    新增聊天记录
    """
    if not message_id:
        message_id = uuid.uuid4().hex
    m = UserMessageModel(
        id=message_id,
        user_id=user_id,
        chat_type=chat_type,
        query=query,
        response=response,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def update_message(session, message_id, response: str = None):
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
def get_message_by_id(session, message_id) -> UserMessageModel:
    """
    查询聊天记录
    """
    m = session.query(UserMessageModel).filter_by(id=message_id).first()
    return m



@with_session
def filter_user_message(session, user_id: str, limit: int = 10):
    messages = (
        session.query(UserMessageModel)
        .filter_by(user_id=user_id)
        .
        # 用户最新的query 也会插入到db，忽略这个message record
        filter(UserMessageModel.response != "")
        .
        # 返回最近的limit 条记录
        order_by(UserMessageModel.create_time.desc())
        .limit(limit)
        .all()
    )
    # 直接返回 List[MessageModel] 报错
    data = []
    for m in messages:
        data.append({"query": m.query, "response": m.response})
    return data
