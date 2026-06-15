from typing import TypedDict, Literal, List


# ====================== Agent状态定义 ======================
class AgentState(TypedDict):
    query: str
    route: str
    # 时间
    time_desc: str
    start_date: str
    end_date: str
    query_year: int
    query_month: int

    # 【告警中间结果-start】
    current_tool: str | None
    current_params: dict
    # 已执行的工具结果
    tool_results: list[dict]
    # 已调用的工具名称列表（用于避免重复）
    executed_tools: list[str]
    # 【告警中间结果-end】

    rag_context: str  # RAG检索结果
    alert_context: str  # 告警相关查询结果
    final_answer: str

    # 元数据
    chat_history: List[dict]
    conversation_id: str
    msg_id: str
    is_stream: bool
