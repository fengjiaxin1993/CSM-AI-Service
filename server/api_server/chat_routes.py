from __future__ import annotations
from server.chat.similar_mem_chat import similar_mem_chat
from fastapi import APIRouter, Request
from server.chat.chat import chat
from server.chat.kb_chat import kb_chat
from utils import build_logger
from ..chat.mem_chat import mem_chat

logger = build_logger()

chat_router = APIRouter(prefix="/chat", tags=["ChatChat 对话"])

chat_router.post(
    "/chat",
    summary="与llm模型对话(通过LLMChain)",
)(chat)

chat_router.post(
    "/mem_chat",
    summary="与llm模型对话带记忆功能(通过LLMChain)",
)(mem_chat)

chat_router.post(
    "/similar_mem_chat",
    summary="与llm模型对话带记忆功能,similar(通过LLMChain)",
)(similar_mem_chat)

chat_router.post("/kb_chat", summary="知识库对话")(kb_chat)