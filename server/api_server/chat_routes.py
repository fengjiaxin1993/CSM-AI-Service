from __future__ import annotations
from fastapi import APIRouter, Request
from utils import build_logger
from ..chat.mem_chat import mem_chat

logger = build_logger()

chat_router = APIRouter(prefix="/chat", tags=["ChatChat 对话"])

chat_router.post(
    "/mem_chat",
    summary="与llm模型对话带记忆功能(通过LLMChain)",
)(mem_chat)
