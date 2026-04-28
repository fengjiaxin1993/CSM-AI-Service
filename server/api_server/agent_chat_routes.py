from __future__ import annotations
from fastapi import APIRouter, Request
from utils import build_logger
from ..chat.agent_chat import agent_chat

logger = build_logger()

agent_chat_router = APIRouter(prefix="/agent_chat", tags=["agent 对话"])

agent_chat_router.post(
    "/agent_chat",
    summary="智能体对话",
)(agent_chat)