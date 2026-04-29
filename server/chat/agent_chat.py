import json
import uuid
import asyncio
import httpx
import os
from datetime import datetime, timedelta
from typing import TypedDict, List, AsyncIterable, Optional, Dict, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.tools import StructuredTool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, create_model
from fastapi import Body, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse
from langchain_classic.callbacks import AsyncIteratorCallbackHandler

import settings
from server.api_server.api_schemas import OpenAIChatOutput
from server.chat.utils import History
from server.knowledge_base.kb_doc_api import search_docs, search_temp_docs
from server.knowledge_base.kb_cache.faiss_cache import memo_faiss_pool
from server.knowledge_base.utils import KnowledgeFile, format_reference
from server.utils import get_ChatOpenAI, get_prompt_template, wrap_done, get_temp_dir, run_in_thread_pool
from server.db.repository import add_conversation_to_db, filter_conversation
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
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


# ====================== 工具核心代码 ======================
_TYPE_MAP = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}


def _create_schema(params: list):
    """创建Pydantic参数模型"""
    fields = {}
    for p in params:
        fields[p.name] = (_TYPE_MAP.get(p.type, str), Field(
            default=... if p.required else (p.default if p.default is not None else None),
            description=p.description
        ))
    return create_model("Params", __base__=BaseModel, **fields)


def _call_api(name: str, url: str, method: str, headers: dict, timeout: int, payload: dict) -> Optional[str]:
    """同步调用API"""
    base_url = Settings.agent_tools_settings.ALERT_API_BASE_URL
    if not base_url:
        return None

    # 正确处理 URL 拼接，避免双斜杠
    base_url = base_url.rstrip('/')
    url_path = url.lstrip('/')
    full_url = f"{base_url}/{url_path}"

    log(f"API请求: {method.upper()} {full_url}, payload={payload}, headers={headers}")

    try:
        method = method.upper()
        with httpx.Client(timeout=timeout) as client:
            if method == "GET":
                resp = client.get(full_url, params=payload, headers=headers)
            else:
                resp = client.post(full_url, json=payload, headers=headers)
        resp.raise_for_status()
        log(f"API响应: {resp.status_code}")
        return resp.text
    except httpx.TimeoutException as e:
        log(f"API调用超时: {name}, timeout={timeout}s, error={e}")
        return None
    except httpx.ConnectError as e:
        log(f"API连接失败: {name}, url={full_url}, error={e}")
        return None
    except Exception as e:
        log(f"API调用失败: {name}, error={type(e).__name__}: {e}")
        return None


def _mock_data(name: str, start: str, end: str) -> str:
    """生成模拟数据"""
    templates = {
        "overview": {"时间范围": f"{start} ~ {end}", "告警总数": 206, "紧急": 100, "重要": 106},
        "trend": {"时间范围": f"{start} ~ {end}", "每日趋势": [{start: 32}, {end: 28}]},
        "type": {"时间范围": f"{start} ~ {end}", "告警类型": {"跨域访问": 40, "IP扫描": 39}},
        "rank": {"时间范围": f"{start} ~ {end}", "排行": [{"武汉": 190}, {"黄石": 96}]},
    }
    key = "overview" if "overview" in name else "trend" if "trend" in name else "type" if "type" in name else "rank"
    return json.dumps(templates.get(key, {"数据": "模拟数据"}), ensure_ascii=False, indent=2)


def _tool_impl(name: str, url: str, method: str, headers: dict, timeout: int, **kwargs) -> str:
    """工具执行实现"""
    start, end = kwargs.get("start_date", ""), kwargs.get("end_date", "")
    log(f"调用工具: {name} | {start} ~ {end}")

    # 尝试API调用
    if not Settings.agent_tools_settings.USE_MOCK_DATA:
        result = _call_api(name, url, method, headers, timeout, {"start_date": start, "end_date": end})
        if result:
            log(f"✅ API成功: {name}")
            return result

    # 回退到模拟数据
    return _mock_data(name, start, end)


def create_tool(cfg) -> StructuredTool:
    """根据配置创建工具"""
    return StructuredTool(
        name=cfg.name,
        description=f"{cfg.description}\n返回: {cfg.return_description}\n格式: {json.dumps(cfg.return_schema, ensure_ascii=False)}",
        func=lambda **kw: _tool_impl(cfg.name, cfg.url, cfg.method, cfg.headers, cfg.timeout, **kw),
        args_schema=_create_schema(cfg.params),
    )


# 延迟加载工具列表
_alert_tools = None


def get_alert_tools() -> List[StructuredTool]:
    """获取工具列表"""
    global _alert_tools
    if _alert_tools is None:
        _alert_tools = [create_tool(c) for c in Settings.agent_tools_settings.ALERT_TOOLS if c.name]
        log(f"已加载 {len(_alert_tools)} 个工具")
    return _alert_tools


# ====================== Agent状态定义 ======================
class AgentState(TypedDict):
    query: str
    route: str
    time_desc: str
    start_date: str
    end_date: str
    query_year: int
    query_month: int
    alert_response: str
    rag_response: str
    llm_response: str
    file_parse_response: str
    kb_name: str  # 临时知识库ID
    raw_data: str
    final_answer: str
    chat_history: List[dict]
    conversation_id: str


# ====================== 时间解析 ======================
def parse_time(query: str) -> dict:
    """解析时间语义"""
    today = datetime.now().date()
    prompt = get_prompt_template("agent", "time_parse")
    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=0)
    time_type = (ChatPromptTemplate.from_messages(
        [History(role="user", content=prompt).to_msg_template(False)]) | llm).invoke(
        {"question": query}).content.strip()

    log(f"时间类型: {time_type}")

    if time_type == "today":
        start = end = str(today)
        desc = "今日"
    elif time_type == "yesterday":
        start = end = str(today - timedelta(days=1))
        desc = "昨日"
    elif time_type == "last7d":
        start, end = str(today - timedelta(days=6)), str(today)
        desc = "近7天"
    elif time_type == "last30d":
        start, end = str(today - timedelta(days=29)), str(today)
        desc = "近30天"
    elif time_type == "thisMonth":
        start, end = f"{today.year}-{today.month:02d}-01", str(today)
        desc = "本月"
    elif time_type == "lastMonth":
        y, m = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        start = f"{y}-{m:02d}-01"
        end = f"{y}-{m:02d}-{28 if m == 2 else 31 if m in [1, 3, 5, 7, 8, 10, 12] else 30}"
        desc = "上月"
    elif time_type == "thisYear":
        start, end = f"{today.year}-01-01", str(today)
        desc = "今年"
    else:
        start, end = f"{today.year}-{today.month:02d}-01", str(today)
        desc = "本月"

    return {"time_desc": desc, "start_date": start, "end_date": end, "year": today.year, "month": today.month}


# ====================== 节点函数 ======================
def time_parse_node(state: AgentState) -> AgentState:
    data = parse_time(state["query"])
    state.update({**data, "query_year": data["year"], "query_month": data["month"]})
    log(f"时间解析: {data['start_date']} ~ {data['end_date']}")
    return state


def _check_doc_operation_intent(query: str) -> bool:
    """使用大模型判断用户提问是否需要文档操作（总结、提取、解读等）"""
    try:
        prompt = get_prompt_template("agent", "file_related")
        llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=0)
        result = (ChatPromptTemplate.from_messages(
            [History(role="user", content=prompt).to_msg_template(False)]) | llm).invoke(
            {"question": query}).content.strip().upper()
        is_doc_operation = "YES" in result
        log(f"大模型判断文档操作意图: {result} -> {'需要' if is_doc_operation else '不需要'}文档操作")
        return is_doc_operation
    except Exception as e:
        log(f"文档操作意图判断失败: {e}，默认继续其他逻辑")
        return False


def supervisor_node(state: AgentState) -> AgentState:
    log("Supervisor路由判断")
    query = state["query"]
    kb_name = state.get("kb_name", "")

    # 如果有上传文件，先判断问题是否需要文档操作
    if kb_name:
        log(f"检测到文件上传，知识库ID: {kb_name}，判断问题是否需要文档操作...")
        
        # 第一层：使用大模型判断是否需要文档操作
        if _check_doc_operation_intent(query):
            log("大模型判断需要文档操作，路由到 file_parse")
            state["route"] = "file_parse"
            return state
        
        # 第二层：通过向量检索判断内容相关性
        log("大模型判断不需要文档操作，继续通过向量检索判断内容相关性...")
        try:
            docs = search_temp_docs(
                knowledge_id=kb_name,
                query=query,
                top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K,
                score_threshold=Settings.kb_settings.SCORE_THRESHOLD
            )
            if docs:
                log(f"向量检索判断问题与文件内容相关，检索到 {len(docs)} 个相关文档")
                state["route"] = "file_parse"
                return state
            else:
                log("向量检索判断问题与文件内容不相关，继续走原有逻辑")
        except Exception as e:
            log(f"文件相关性判断失败: {e}，继续走原有逻辑")

    # 原有逻辑
    prompt = get_prompt_template("agent", "supervisor")
    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=0)
    state["route"] = (ChatPromptTemplate.from_messages(
        [History(role="user", content=prompt).to_msg_template(False)]) | llm).invoke(
        {"question": query}).content.strip()
    log(f"路由结果: {state['route']}")
    return state


def alert_agent(state: AgentState) -> AgentState:
    log("===== 告警智能体 =====")
    tools = get_alert_tools()
    if not tools:
        state["alert_response"] = "未配置告警工具"
        return state

    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=Settings.model_settings.TEMPERATURE)
    llm_with_tools = llm.bind_tools(tools)

    system = f"查询时间范围：{state['start_date']} ~ {state['end_date']}，调用对应告警工具"
    resp = (ChatPromptTemplate.from_messages([("system", system), ("user", "{query}")]) | llm_with_tools).invoke(
        {"query": state["query"]})

    results = []
    for call in resp.tool_calls:
        tool = next((t for t in tools if t.name == call["name"]), None)
        if tool:
            args = call["args"]
            args.update({"start_date": state["start_date"], "end_date": state["end_date"]})
            result = tool.invoke(args)
            log(f"工具返回 [{tool.name}]: {result[:200]}..." if len(
                result) > 200 else f"工具返回 [{tool.name}]: {result}")
            results.append(result)

    state["alert_response"] = "\n".join(results)
    log(f"告警Agent结果【总结】: {state['alert_response'][:200]}..." if len(
        state['alert_response']) > 200 else f"告警Agent结果: {state['alert_response']}")
    return state


def rag_agent(state: AgentState) -> AgentState:
    log("===== RAG智能体 =====")
    docs = search_docs(
        query=state["query"],
        knowledge_base_name=Settings.kb_settings.DEFAULT_KNOWLEDGE_BASE,
        top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K,
        score_threshold=Settings.kb_settings.SCORE_THRESHOLD
    )
    context = "\n\n".join([d["page_content"] for d in docs])
    log(f"检索到 {len(docs)} 个文档")
    if docs:
        log(f"检索内容预览: {context[:200]}..." if len(context) > 200 else f"检索内容: {context}")

    prompt_name = "empty" if not docs else "default"
    prompt = get_prompt_template("rag", prompt_name)
    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=Settings.model_settings.TEMPERATURE)
    state["rag_response"] = (
            ChatPromptTemplate.from_messages(
                [History(role="user", content=prompt).to_msg_template(False)]) | llm).invoke(
        {"context": context, "question": state["query"]}).content
    log(f"RAG生成结果: {state['rag_response'][:200]}..." if len(
        state['rag_response']) > 200 else f"RAG生成结果: {state['rag_response']}")
    return state


def llm_agent(state: AgentState) -> AgentState:
    log("===== 通用LLM =====")
    prompt = get_prompt_template("llm_model", "default")
    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=Settings.model_settings.TEMPERATURE)
    state["llm_response"] = (
            ChatPromptTemplate.from_messages(
                [History(role="user", content=prompt).to_msg_template(False)]) | llm).invoke(
        {"input": state["query"]}).content
    return state


def file_parse_agent(state: AgentState) -> AgentState:
    log("===== 文件解析智能体 =====")
    kb_name = state.get("kb_name", "")

    if not kb_name:
        state["file_parse_response"] = "未提供知识库ID，无法检索文件内容"
        return state

    try:
        # 从临时知识库中检索文档
        docs = search_temp_docs(
            knowledge_id=kb_name,
            query=state["query"],
            top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K,
            score_threshold=Settings.kb_settings.SCORE_THRESHOLD
        )
        context = "\n\n".join([d["page_content"] for d in docs])
        log(f"文件解析检索到 {len(docs)} 个文档")
        if docs:
            log(f"检索内容预览: {context[:200]}..." if len(context) > 200 else f"检索内容: {context}")

        # 使用RAG方式生成回答
        prompt_name = "empty" if not docs else "default"
        prompt = get_prompt_template("rag", prompt_name)
        llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=Settings.model_settings.TEMPERATURE)
        state["file_parse_response"] = (
                ChatPromptTemplate.from_messages([History(role="user", content=prompt).to_msg_template(False)]) | llm
        ).invoke({"context": context, "question": state["query"]}).content

        log(f"文件解析生成结果: {state['file_parse_response'][:200]}..." if len(
            state['file_parse_response']) > 200 else f"文件解析生成结果: {state['file_parse_response']}")
    except Exception as e:
        log(f"文件解析失败: {e}")
        state["file_parse_response"] = f"文件解析失败: {str(e)}"

    return state


def merge_node(state: AgentState) -> AgentState:
    log("合并结果")
    route = state["route"]
    if route == "alert":
        raw = state["alert_response"]
    elif route == "rag":
        raw = state["rag_response"]
    elif route == "file_parse":
        raw = state["file_parse_response"]
    else:
        raw = state["llm_response"]

    log(f"原始数据: {raw[:200]}..." if len(raw) > 200 else f"原始数据: {raw}")

    if route == "alert":
        log("调用润色模型整理告警结果...")
        try:
            prompt = get_prompt_template("agent", "alert_polish")
            llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL,
                                 temperature=Settings.model_settings.TEMPERATURE)
            final = (ChatPromptTemplate.from_messages(
                [History(role="user", content=prompt).to_msg_template(False)]) | llm).invoke(
                {"question": raw}).content.strip()
            log("润色完成")
        except:
            final = raw
            log("润色失败，使用原始数据")
    else:
        final = raw

    state["raw_data"] = raw
    state["final_answer"] = final
    log(f"最终答案: {final[:200]}..." if len(final) > 200 else f"最终答案: {final}")
    return state


def save_history(state: AgentState) -> AgentState:
    state["chat_history"].append({"user": state["query"], "answer": state["final_answer"]})
    if len(state["chat_history"]) > 10:
        state["chat_history"].pop(0)
    return state


# ====================== 构建工作流 ======================
def create_agent():
    workflow = StateGraph(AgentState)

    for name, func in [("supervisor", supervisor_node), ("time_parse", time_parse_node),
                       ("alert_agent", alert_agent), ("rag_agent", rag_agent),
                       ("file_parse_agent", file_parse_agent), ("llm_agent", llm_agent),
                       ("merge", merge_node), ("save_history", save_history)]:
        workflow.add_node(name, func)

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges("supervisor",
                                   lambda s: "time_parse" if s["route"] == "alert" else s["route"],
                                   {"time_parse": "time_parse", "rag": "rag_agent", "file_parse": "file_parse_agent",
                                    "llm": "llm_agent"})
    workflow.add_edge("time_parse", "alert_agent")
    for node in ["alert_agent", "rag_agent", "file_parse_agent", "llm_agent"]:
        workflow.add_edge(node, "merge")
    workflow.add_edge("merge", "save_history")
    workflow.add_edge("save_history", END)

    return workflow.compile()


# ====================== API接口 ======================


async def agent_chat(
        query: str = Body("最近7天告警情况如何", description="用户问题"),
        stream: bool = Body(False, description="流式输出"),
        conversation_id: str = Body("test1", description="对话框id"),
        kb_name: str = Body("", description="临时知识库ID，用于文件解析，通过upload_agent_files接口获取")
):
    """电力告警智能体对话接口"""

    # 优先使用 file_id，如果没有则使用 kb_name

    async def iterator() -> AsyncIterable[str]:
        log(f"\n========== 请求开始: {query} ==========")
        log(f"知识库ID: {kb_name if kb_name else '无'}")

        msg_id = add_conversation_to_db(conversation_id, "agent_chat", query, "")

        history = []
        if conversation_id:
            history = [{"user": r["query"], "answer": r["response"]} for r in
                       filter_conversation(conversation_id, limit=10)]
            log(f"历史记录: {len(history)}条")

        agent = create_agent()

        if not stream:
            # 非流式
            state = agent.invoke({
                "query": query, "route": "", "time_desc": "", "start_date": "", "end_date": "",
                "query_year": 0, "query_month": 0, "alert_response": "", "rag_response": "",
                "file_parse_response": "", "kb_name": kb_name, "llm_response": "", "raw_data": "",
                "final_answer": "", "chat_history": history, "conversation_id": conversation_id
            })
            from server.db.repository import update_conversation
            update_conversation(msg_id, state["final_answer"])
            yield OpenAIChatOutput(id=f"chat{uuid.uuid4()}", object="chat.completion", content=state["final_answer"],
                                   role="assistant", model=Settings.model_settings.DEFAULT_LLM_MODEL).model_dump_json()
            return

        # 流式处理
        supervisor_state = supervisor_node(
            {"query": query, "route": "", "time_desc": "", "start_date": "", "end_date": "", "query_year": 0,
             "query_month": 0, "alert_response": "", "rag_response": "", "file_parse_response": "",
             "kb_name": kb_name, "llm_response": "", "raw_data": "", "final_answer": "", "chat_history": history,
             "conversation_id": conversation_id})
        route = supervisor_state["route"]

        if route == "alert":
            state = alert_agent(time_parse_node(supervisor_state.copy()))
            raw_data = state["alert_response"]
            log("调用润色模型整理告警结果...")
            prompt = get_prompt_template("agent", "alert_polish")
        elif route == "rag":
            state = supervisor_state.copy()
            docs = search_docs(query, Settings.kb_settings.DEFAULT_KNOWLEDGE_BASE,
                                                                  Settings.kb_settings.VECTOR_SEARCH_TOP_K,
                                                                  Settings.kb_settings.SCORE_THRESHOLD)
            context = "\n\n".join([d["page_content"] for d in docs])
            log(f"流式RAG检索到 {len(docs)} 个文档")
            if docs:
                log(f"流式RAG检索内容预览: {context[:200]}..." if len(context) > 200 else f"流式RAG检索内容: {context}")
            prompt_name = "empty" if not docs else "default"
            prompt = get_prompt_template("rag", prompt_name)
            raw_data = f"[RAG检索到{len(docs)}个文档]"
            log(f"合并结果 | RAG路由: {raw_data}")
        elif route == "file_parse":
            state = supervisor_state.copy()
            loop = asyncio.get_event_loop()
            if kb_name:
                docs = search_temp_docs(kb_name, query, Settings.kb_settings.VECTOR_SEARCH_TOP_K,
                                                                  Settings.kb_settings.SCORE_THRESHOLD)
                context = "\n\n".join([d["page_content"] for d in docs])
                log(f"流式文件解析检索到 {len(docs)} 个文档")
                if docs:
                    log(f"流式文件解析检索内容预览: {context[:200]}..." if len(
                        context) > 200 else f"流式文件解析检索内容: {context}")
            else:
                docs = []
                context = ""
                log("未提供知识库ID，无法进行文件解析")
            prompt_name = "empty" if not docs else "default"
            prompt = get_prompt_template("rag", prompt_name)
            raw_data = f"[文件解析检索到{len(docs)}个文档]"
            log(f"合并结果 | 文件解析路由: {raw_data}")
        else:
            state = supervisor_state.copy()
            log("合并结果 | 直接使用LLM回复")
            prompt = get_prompt_template("llm_model", "default")
            raw_data = "[通用LLM回复]"

        # 流式生成
        callback = AsyncIteratorCallbackHandler()
        conv_callback = ConversationCallbackHandler(conversation_id, msg_id, "agent_chat", query)

        llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=Settings.model_settings.TEMPERATURE,
                             callbacks=[callback, conv_callback], streaming=True)

        if route == "alert":
            task = asyncio.create_task(wrap_done(
                (ChatPromptTemplate.from_messages(
                    [History(role="user", content=prompt).to_msg_template(False)]) | llm).ainvoke(
                    {"question": raw_data}), callback.done))
        elif route == "rag" or route == "file_parse":
            task = asyncio.create_task(wrap_done(
                (ChatPromptTemplate.from_messages(
                    [History(role="user", content=prompt).to_msg_template(False)]) | llm).ainvoke(
                    {"context": context, "question": query}), callback.done))
        else:
            task = asyncio.create_task(wrap_done(
                (ChatPromptTemplate.from_messages(
                    [History(role="user", content=prompt).to_msg_template(False)]) | llm).ainvoke(
                    {"input": query}), callback.done))

        full = ""
        async for token in callback.aiter():
            full += token
            yield OpenAIChatOutput(id=f"chat{uuid.uuid4()}", object="chat.completion.chunk", content=token,
                                   role="assistant", model=Settings.model_settings.DEFAULT_LLM_MODEL).model_dump_json()

        await task
        save_history({**state, "final_answer": full})

    return EventSourceResponse(iterator()) if stream else await iterator().__anext__()
