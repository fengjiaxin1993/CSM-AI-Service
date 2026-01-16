import uuid
from server.db.models.conversation_model import ConversationModel
from server.db.session import with_session


@with_session
def add_conversation_to_db(
        session,
        conversation_id: str,
        chat_type,
        query,
        response="",
        message_id=None
):
    """
    新增聊天记录
    """
    if not message_id:
        message_id = uuid.uuid4().hex
    m = ConversationModel(id=message_id,
        chat_type=chat_type,
        query=query,
        response=response,
        conversation_id=conversation_id
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def update_conversation(session, message_id, response: str = None):
    """
    更新已有的聊天记录
    """
    m = get_conversation_by_id(message_id)
    if m is not None:
        if response is not None:
            m.response = response
        session.add(m)
        session.commit()
        return m.id


@with_session
def get_conversation_by_id(session, message_id) -> ConversationModel:
    """
    查询聊天记录
    """
    m = session.query(ConversationModel).filter_by(id=message_id).first()
    return m


@with_session
def filter_conversation(session, conversation_id: str, limit: int = 10):
    messages = (
        session.query(ConversationModel)
        .filter_by(conversation_id=conversation_id)
        .
        # 用户最新的query 也会插入到db，忽略这个message record
        filter(ConversationModel.response != "")
        .
        # 返回最近的limit 条记录
        order_by(ConversationModel.create_time.desc())
        .limit(limit)
        .all()
    )
    # 直接返回 List[MessageModel] 报错
    data = []
    for m in messages:
        data.append({"query": m.query, "response": m.response})
    return data