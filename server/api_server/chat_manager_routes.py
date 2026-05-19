from __future__ import annotations
from fastapi import APIRouter
from utils import build_logger
from server.chat_manager.chat_manager import (
    get_possible_questions,
    get_user_conversations,
    get_conversation_messages,
    delete_conversation,
    save_conversation,
    toggle_conversation_favorite,
)

logger = build_logger()

chat_manager_router = APIRouter(prefix="/chat_manager", tags=["会话管理"])

# 1. 获取可能的提问
chat_manager_router.post(
    "/possible_questions",
    summary="获取可能的提问列表",
)(get_possible_questions)

# 2. 获取用户最近的对话列表
chat_manager_router.post(
    "/conversations",
    summary="获取用户最近的对话列表",
)(get_user_conversations)

# 3. 获取某个会话的对话内容
chat_manager_router.post(
    "/conversation/messages",
    summary="获取某个会话的所有对话内容",
)(get_conversation_messages)

# 4. 删除会话
chat_manager_router.post(
    "/conversation/delete",
    summary="删除会话",
)(delete_conversation)

# 5. 给本次会话生成名称
chat_manager_router.post(
    "/conversation/save_conversation",
    summary="保存本次会话",
)(save_conversation)

# 6. 给会话增加收藏标记
chat_manager_router.post(
    "/conversation/toggle_favorite",
    summary="给会话增加或取消收藏标记",
)(toggle_conversation_favorite)
