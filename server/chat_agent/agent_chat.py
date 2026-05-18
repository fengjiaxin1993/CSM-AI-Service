import uuid
import asyncio
from typing import AsyncIterable
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from fastapi import Body
from sse_starlette.sse import EventSourceResponse
from langchain_classic.callbacks import AsyncIteratorCallbackHandler
import settings
from server.api_server.api_schemas import OpenAIChatOutput
from server.callback_handler.message_callback_handler import MessageCallbackHandler
from server.chat.utils import History
from server.chat_agent.agentStatus import AgentState
from server.chat_agent.node import supervisor_node, time_parse_node, rag_agent_node, llm_agent_node, alert_agent_node
from server.utils import get_ChatOpenAI, get_prompt_template, wrap_done
from server.db.repository import add_message_to_db, filter_message, conversation_repository
from settings import Settings
from utils import build_logger

logger = build_logger()


def log(msg: str):
    """全局日志打印"""
    try:
        if getattr(settings.BasicSettings, "PRINT_AGENT", True):
            logger.info(f"\n[🔎 运行日志] {msg}")
    except:
        logger.info(f"\n[🔎 运行日志] {msg}")


def save_history(state: AgentState) -> AgentState:
    state["chat_history"].append({"user": state["query"], "answer": state["final_answer"]})
    if len(state["chat_history"]) > 10:
        state["chat_history"].pop(0)
    return state


# ====================== 构建工作流（不包含答案生成）=====================
def create_agent():
    """创建智能体工作流 - 只执行到数据收集阶段"""
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("time_parse", time_parse_node)
    workflow.add_node("alert_agent", alert_agent_node)
    workflow.add_node("rag_agent", rag_agent_node)
    workflow.add_node("llm_agent", llm_agent_node)

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges("supervisor",
                                   lambda s: "time_parse" if s["route"] == "alert" else s["route"],
                                   {"time_parse": "time_parse", "rag": "rag_agent", "llm": "llm_agent"})
    workflow.add_edge("time_parse", "alert_agent")
    workflow.add_edge("alert_agent", END)
    workflow.add_edge("rag_agent", END)
    workflow.add_edge("llm_agent", END)

    return workflow.compile()


# ====================== 答案生成 ======================
def generate_answer_sync(state: AgentState) -> str:
    """同步生成最终答案"""
    route = state.get("route", "llm")
    query = state["query"]

    log(f"===== 📝 生成最终答案 [{route}] =====")

    if route == "alert":
        prompt = get_prompt_template("agent", "alert_polish")
        alert_context = state.get("alert_context", "未获取告警数据")
        context_vars = {"question": query, "alert_context": alert_context}
        log(f"告警上下文长度: {len(alert_context)} 字符")

    elif route == "rag":
        context = state.get("rag_context", "")
        prompt_name = "empty" if not context else "default"
        prompt = get_prompt_template("rag", prompt_name)
        context_vars = {"context": context, "question": query}
        log(f"RAG上下文长度: {len(context)} 字符")

    else:  # llm
        prompt = get_prompt_template("llm_model", "default")
        context_vars = {"input": query}
        log("使用通用LLM回复")

    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=Settings.model_settings.TEMPERATURE)
    chain = ChatPromptTemplate.from_messages([History(role="user", content=prompt).to_msg_template(False)]) | llm

    try:
        response = chain.invoke(context_vars)
        answer = response.content if hasattr(response, 'content') else str(response)
        log(f"✅ 答案生成完成，长度: {len(answer)} 字符")
        return answer
    except Exception as e:
        log(f"❌ 答案生成失败: {e}")
        return "抱歉，生成答案时发生错误，请稍后重试。"


# ====================== API接口 ======================


async def agent_chat(
        query: str = Body("最近7天告警情况如何", description="用户问题"),
        stream: bool = Body(False, description="流式输出"),
        conversation_id: str = Body("test1", description="对话框ID"),
        user_id: str = Body("user1", description="用户ID")
):
    """电力告警智能体对话接口"""

    log(f"========== 请求开始: {query} [stream={stream}] ==========")
    msg_id = add_message_to_db(conversation_id, query, "")

    history = []
    if conversation_id:
        history = [{"user": r["query"], "answer": r["response"]} for r in
                   filter_message(conversation_id, limit=10, offset=0)]
        log(f"历史记录: {len(history)}条")

    agent = create_agent()

    # 初始化状态
    init_state = {
        "query": query, "route": "",
        "time_desc": "", "start_date": "", "end_date": "", "query_year": 0, "query_month": 0,
        "current_tool": "", "current_params": {}, "tool_results": [], "executed_tools": [],
        "alert_context": "", "rag_context": "", "final_answer": "",
        "chat_history": history, "conversation_id": conversation_id, "is_stream": stream,
        "msg_id": msg_id
    }

    if not stream:
        # 非流式：执行工作流 + 同步生成答案
        state = agent.invoke(init_state)
        answer = generate_answer_sync(state)
        state["final_answer"] = answer

        from server.db.repository import update_response_message
        update_response_message(msg_id, answer)
        if not conversation_repository.conversation_exists(conversation_id=conversation_id):
            conversation_repository.create_conversation(conversation_id=conversation_id, user_id=user_id)


        save_history(state)

        return OpenAIChatOutput(
            id=f"chat{uuid.uuid4()}",
            object="chat.completion",
            content=answer,
            role="assistant",
            model=Settings.model_settings.DEFAULT_LLM_MODEL
        ).model_dump_json()
    else:
        # 流式处理 - 仿照 agent_chat.py.bak 的实现
        async def iterator() -> AsyncIterable[str]:
            try:
                state = agent.invoke(init_state.copy())
            except Exception as e:
                log(f"❌ 智能体节点执行失败: {e}")
                yield OpenAIChatOutput(
                    id=f"chat{uuid.uuid4()}",
                    object="chat.completion",
                    content="抱歉，服务暂时不可用，请检查LLM模型配置和网络连接。",
                    role="assistant",
                    model=Settings.model_settings.DEFAULT_LLM_MODEL
                ).model_dump_json()
                return

            # 根据路由执行对应的数据收集逻辑
            route = state.get("route", "llm")
            query = state["query"]

            if route == "alert":
                prompt = get_prompt_template("agent", "alert_polish")
                alert_context = state.get("alert_context", "未获取告警数据")
                context_vars = {"question": query, "alert_context": alert_context}
            elif route == "rag":
                context = state.get("rag_context", "")
                prompt_name = "empty" if not context else "default"
                prompt = get_prompt_template("rag", prompt_name)
                context_vars = {"context": context, "question": query}
            else:  # llm
                prompt = get_prompt_template("llm_model", "default")
                context_vars = {"input": query}

            # 流式生成
            callback = AsyncIteratorCallbackHandler()
            message_callback = MessageCallbackHandler(conversation_id=conversation_id, message_id=msg_id, user_id=user_id, query=query)

            llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL,
                                 temperature=Settings.model_settings.TEMPERATURE,
                                 callbacks=[callback, message_callback], streaming=True)

            chain = ChatPromptTemplate.from_messages(
                [History(role="user", content=prompt).to_msg_template(False)]) | llm
            task = asyncio.create_task(wrap_done(chain.ainvoke(context_vars), callback.done))

            full = ""
            async for token in callback.aiter():
                full += token
                yield OpenAIChatOutput(
                    id=f"chat{uuid.uuid4()}",
                    object="chat.completion.chunk",
                    content=token,
                    role="assistant",
                    model=Settings.model_settings.DEFAULT_LLM_MODEL
                ).model_dump_json()

            await task
            state["final_answer"] = full
            save_history(state)

    return EventSourceResponse(iterator())
