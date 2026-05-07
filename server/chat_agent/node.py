from datetime import datetime, timedelta
from langchain_core.prompts import ChatPromptTemplate
import settings
from server.chat.utils import History
from server.chat_agent.agentStatus import AgentState
from server.chat_agent.alert_agent import AlertAgent
from server.knowledge_base.kb_doc_api import search_docs
from server.utils import get_ChatOpenAI, get_prompt_template
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


# ====================== 时间解析 ======================
def parse_time(query: str) -> dict:
    """解析时间语义 - 使用LLM结合当前时间智能判断"""
    from datetime import datetime
    now = datetime.now()
    today = now.date()
    
    # 构建详细的提示词
    time_parse_prompt = f"""你是一个时间解析助手。请根据用户的查询语句和当前时间，判断用户希望查询的时间范围。

当前时间信息：
- 当前日期：{today.strftime('%Y-%m-%d')}
- 当前年份：{today.year}
- 当前月份：{today.month}
- 当前日期：{today.day}
- 今天是星期{today.weekday() + 1}（1=周一，7=周日）

用户查询："{query}"

请分析用户查询中的时间语义，可能的时间表达包括：
- 相对时间：今天、昨天、明天、最近7天、最近N天、最近30天、本周、上周、本月、上月、今年、去年
- 绝对时间：2024年1月、2024-01-01、1月1日等具体日期
- 特殊表达：年初、年末、月初、月末、周末等

请以JSON格式返回解析结果：
{{
    "start_date": "开始日期(YYYY-MM-DD格式)",
    "end_date": "结束日期(YYYY-MM-DD格式)",
    "time_desc": "时间描述(如:今日、近7天、2024年1月等)",
    "reason": "解析原因说明"
}}

注意：
1. 所有日期必须使用YYYY-MM-DD格式
2. 相对时间要基于当前日期{today}计算
3. 如果用户没有明确时间，默认返回本月范围
4. 必须返回合法的JSON格式"""

    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=0)
    
    try:
        response = llm.invoke(time_parse_prompt).content.strip()
        log(f"时间解析LLM响应:\n{response}")
        
        # 提取JSON
        import json
        import re
        json_match = re.search(r'\{.*?\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            start_date = result.get("start_date", "")
            end_date = result.get("end_date", "")
            time_desc = result.get("time_desc", "")
            reason = result.get("reason", "")
            
            # 验证日期格式
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                log(f"日期格式无效，使用默认值")
                start_date = f"{today.year}-{today.month:02d}-01"
                end_date = str(today)
                time_desc = "本月"
            
            log(f"时间解析结果: {time_desc} ({start_date} ~ {end_date}), 原因: {reason}")
            return {
                "time_desc": time_desc,
                "start_date": start_date,
                "end_date": end_date,
            }
    except Exception as e:
        log(f"时间解析失败: {e}，使用默认本月")
    
    # 默认返回本月
    return {
        "time_desc": "本月",
        "start_date": f"{today.year}-{today.month:02d}-01",
        "end_date": str(today),
    }


# ====================== 节点函数 ======================
def time_parse_node(state: AgentState) -> AgentState:
    data = parse_time(state["query"])
    log(f"时间解析: {data['start_date']} ~ {data['end_date']}")
    state.update({**data, "start_date": data["start_date"], "end_date": data["end_date"]})
    return state


def supervisor_node(state: AgentState) -> AgentState:
    log("🎯 Supervisor开始意图识别")
    query = state["query"]

    prompt = get_prompt_template("agent", "supervisor")
    llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL, temperature=0)
    route = (ChatPromptTemplate.from_messages(
        [History(role="user", content=prompt).to_msg_template(False)]) | llm).invoke(
        {"question": query}).content.strip().lower()
    if "alert" in route:
        state["route"] = "alert"
    elif "rag" in route:
        state["route"] = "rag"
    else:
        state["route"] = "llm"

    log(f"🎯 意图识别结果: {state['route']}")
    return state


def alert_agent_node(state: AgentState) -> AgentState:
    """告警智能体节点 - 使用AlertAgent循环调用工具"""
    log("=====🔧 告警智能体节点 =====")

    alert_agent = AlertAgent()
    result_state = alert_agent.run(state)

    log(f"告警Agent结果:\n{result_state.get('alert_context', '')}\n")
    return result_state


def rag_agent_node(state: AgentState) -> AgentState:
    log("=====📚RAG智能体 =====")
    docs = search_docs(
        query=state["query"],
        knowledge_base_name=Settings.kb_settings.DEFAULT_KNOWLEDGE_BASE,
        top_k=Settings.kb_settings.VECTOR_SEARCH_TOP_K,
        score_threshold=Settings.kb_settings.SCORE_THRESHOLD
    )
    context = "\n\n".join([d["page_content"] for d in docs])
    log(f"检索到 {len(docs)} 个文档")
    state["rag_context"] = context
    return state


def llm_agent_node(state: AgentState) -> AgentState:
    log("=====💬通用LLM =====")
    return state
