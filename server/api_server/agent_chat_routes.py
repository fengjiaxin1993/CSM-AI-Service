from __future__ import annotations
from fastapi import APIRouter, Request
from utils import build_logger
from ..chat_agent.agent_chat import agent_chat

logger = build_logger()

agent_chat_router = APIRouter(prefix="/chat_agent", tags=["agent 对话"])

agent_chat_router.post(
    "/chat_agent",
    summary="智能体对话",
)(agent_chat)