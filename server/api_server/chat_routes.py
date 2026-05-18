from __future__ import annotations
from server.chat.similar_mem_chat import similar_mem_chat
from fastapi import APIRouter, Body
from server.chat.chat import chat
from server.chat.kb_chat import kb_chat
from settings import Settings
from utils import build_logger
from ..chat.mem_chat import mem_chat
from ..chat_agent.agent_chat import agent_chat

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

(chat_router.post(
    "/kb_chat",
    summary="知识库对话")
 (kb_chat))


chat_router.post(
    "/chat_agent",
    summary="智能体对话",
)(agent_chat)


# ============ 统一对话接口 ============
async def unified_chat(
        # 通用参数（Form格式，兼容文件上传）
        query: str = Body("最近7天告警情况如何", description="用户问题"),
        stream: bool = Body(False, description="流式输出"),
        conversation_id: str = Body("test1", description="对话框ID"),
        user_id: str = Body("user1", description="用户ID"),
        # KB 相关参数
        kb_name: str = Body("", description="临时知识库ID"),

):
    """
    统一对话接口
    """
    # 判断使用哪种模式
    if kb_name:
        logger.info(f"[unified_chat] 使用临时对话模式")
        # 调用 kb_chat
        return await kb_chat(
            query=query,
            mode="temp_kb",
            kb_name=kb_name,
            return_direct=False,
        )
    else:
        # 智能体对话模式
        logger.info(f"[unified_chat] 使用智能体对话模式")

        return await agent_chat(
            query=query,
            stream=stream,
            conversation_id=conversation_id,
            user_id=user_id,
        )


chat_router.post(
    "/unified_chat",
    summary="统一对话接口（有文件走知识库，无文件走智能体）",
    description="""
统一对话接口，自动根据是否有文件上传选择对话模式：
- 有文件上传：走知识库对话 (kb_chat)，文件会自动上传到临时知识库
- 无文件上传：走智能体对话 (agent_chat)
""",
)(unified_chat)