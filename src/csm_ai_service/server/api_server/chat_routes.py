from __future__ import annotations
from csm_ai_service.server.conversation.chat.similar_mem_chat import similar_mem_chat
from fastapi import APIRouter, Body
from csm_ai_service.server.conversation.chat.chat import chat
from csm_ai_service.server.conversation.chat.kb_chat import kb_chat
from csm_ai_service.utils import build_logger
from csm_ai_service.server.conversation.chat.file_chat import file_chat
from csm_ai_service.server.conversation.chat.mem_chat import mem_chat
from csm_ai_service.server.conversation.chat_agent.agent_chat import agent_chat

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
        # file_id 相关参数
        file_id: str = Body("", description="临时知识库ID"),

):
    """
    统一对话接口
    """
    # 判断使用哪种模式
    if file_id:
        logger.info(f"[unified_chat] 使用临时对话模式")
        # 调用 kb_chat
        return await file_chat(
            query=query,
            file_id=file_id,
            stream=stream,
            conversation_id=conversation_id
        )
    else:
        # 智能体对话模式
        logger.info(f"[unified_chat] 使用智能体对话模式")

        return await agent_chat(
            query=query,
            stream=stream,
            conversation_id=conversation_id,
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