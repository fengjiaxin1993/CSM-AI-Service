import json
import requests
from typing import Literal
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END

import csm_ai_service.settings
from csm_ai_service.server.conversation.chat_agent.agentStatus import AgentState
from csm_ai_service.server.utils import get_ChatOpenAI
from csm_ai_service.settings import Settings, AlertToolConfig
from csm_ai_service.utils import build_logger

logger = build_logger()


def log(msg: str):
    """全局日志打印"""
    try:
        if getattr(settings.BasicSettings, "PRINT_AGENT", True):
            logger.info(f"\n[🔎 运行日志] {msg}")
    except:
        logger.info(f"\n[🔎 运行日志] {msg}")


def make_api_caller(tool_config: AlertToolConfig):
    """创建API调用函数"""

    def caller(**kwargs):
        try:
            url = tool_config.url
            method = tool_config.method.upper()
            headers = {"Content-Type": "application/json", "User": "00616400000082"}

            if method == "GET":
                res = requests.get(url, headers=headers, params=kwargs, timeout=tool_config.timeout)
            else:
                res = requests.post(url, json=kwargs, headers=headers, timeout=tool_config.timeout)

            return {
                "tool": tool_config.name,
                "status": "success" if res.status_code == 200 else "error",
                "data": res.json() if res.text else {}
            }
        except Exception as e:
            return {"tool": tool_config.name, "status": "error", "error": str(e)}

    return caller


def build_tools():
    """构建工具函数字典"""
    tool_funcs = {}
    for c in Settings.agent_tools_settings.ALERT_TOOLS:
        name = c.name
        tool_funcs[name] = {
            "func": make_api_caller(c),
            "desc": c.description,
            "params": c.params}

    return tool_funcs


def build_tool_descriptions(tools) -> str:
    """构建工具描述文本，包含参数类型"""
    lines = []
    for name, info in tools.items():
        lines.append(f"- {name}: {info['desc']}")
        lines.append(f"  参数:")
        param_list = info['params']
        for p in param_list:
            name = p.name
            param_type = p.type
            required = "必填" if p.required else "可选"
            desc = p.description
            lines.append(f"    - {name}: 类型={param_type}, {required}, 说明={desc}")
    return "\n".join(lines)


class AlertAgent:
    def __init__(self, name: str = "告警智能体", max_iter: int = 2):
        self.name = name
        self.max_iter = max_iter  # 单次最多调用工具次数
        self.tools = build_tools()
        self.llm = get_ChatOpenAI(Settings.model_settings.DEFAULT_LLM_MODEL,
                                  temperature=Settings.model_settings.TEMPERATURE)
        self.graph = self._build_graph()

    # ==============================
    # 节点函数
    # ==============================
    def _select_tool(self, state: AgentState) -> AgentState:
        """
        选择工具 - 基于已有结果，决定是否需要调用更多工具
        """
        log(f"===== 🔧 工具选择 =====")

        tools_desc = build_tool_descriptions(self.tools)
        executed = state.get("executed_tools", [])
        results = state.get("tool_results", [])

        # 构建已执行工具的结果摘要
        results_summary = ""
        if results:
            results_summary = "\n\n已获取的数据：\n"
            for r in results:
                tool_name = r.get("tool", "unknown")
                if r.get("status") == "success":
                    data_str = json.dumps(r.get("data", {}), ensure_ascii=False)[:200]
                    results_summary += f"- {tool_name}: {data_str}...\n"
                else:
                    results_summary += f"- {tool_name}: 调用失败 - {r.get('error', '未知错误')}\n"

        # 构建提示词
        prompt = f"""你是告警数据分析助手。根据用户问题和已获取的数据，判断是否需要调用更多工具。
查询时间范围：{state['start_date']} ~ {state['end_date']}
用户问题：{state['query']}

可用工具：
{tools_desc}
{results_summary}

已调用的工具：{executed if executed else '无'}

请判断：
1. 如果还需要更多数据，返回下一个要调用的工具
2. 如果数据已足够，返回不需要更多工具

请以JSON格式返回：
{{"tool_name": "工具名称", "parameters": {{"参数名": "值"}}, "need_more": true/false, "reason": "选择原因"}}

注意：
- tool_name: 要调用的工具名，如果不需要更多工具则填 null
- parameters: 工具参数
- need_more: 是否需要继续调用更多工具
- reason: 简要说明选择原因"""

        log(f"🤖 正在分析... 已调用{len(executed)}个工具")
        response = self.llm.invoke([HumanMessage(content=prompt)]).content.strip()
        log(f"📤 LLM响应:\n {response}")

        # 解析JSON
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(response[start:end + 1])
                tool_name = data.get("tool_name")
                params = data.get("parameters", {})
                need_more = data.get("need_more", False)
                reason = data.get("reason", "")

                # 检查是否重复调用
                if tool_name and tool_name in executed:
                    log(f"⚠️ 工具 {tool_name} 已调用过，跳过")
                    state["current_tool"] = None
                    state["current_params"] = {}
                    state["tool_results"] = results
                    state["executed_tools"] = executed

                    return state

                if tool_name and tool_name in self.tools:
                    log(f"✅ 选择工具: {tool_name}, need_more={need_more}")
                    if reason:
                        log(f"  原因: {reason}")
                    state["current_tool"] = tool_name
                    state["current_params"] = params
                    state["tool_results"] = results
                    state["executed_tools"] = executed

                    return state
        except Exception as e:
            log(f"❌ 解析失败: {e}")

        log("ℹ️ 不需要更多工具")
        state["current_tool"] = None
        state["current_params"] = {}
        state["tool_results"] = results
        state["executed_tools"] = executed
        return state

    def _execute_tool(self, state: AgentState) -> AgentState:
        """执行工具"""
        tool_name = state.get("current_tool")
        if not tool_name or tool_name not in self.tools:
            return state

        log(f"===== ⚙️ 执行工具 =====")
        log(f"🔨 执行: {tool_name}")

        params = state.get("current_params", {})

        # 执行API调用
        result = self.tools[tool_name]["func"](**params)

        # 打印结果
        result_str = json.dumps(result, ensure_ascii=False)
        log(f"📄 结果: {result_str}")
        # 更新结果列表
        results = state.get("tool_results", [])
        results.append(result)

        # 更新已执行工具列表
        executed = state.get("executed_tools", [])
        executed.append(tool_name)

        state["current_tool"] = None
        state["current_params"] = {}
        state["tool_results"] = results
        state["executed_tools"] = executed
        return state

    def _route_after_execute(self, state: AgentState) -> Literal["select_tool", "finalize"]:
        """路由：执行工具后，判断是否需要继续选择工具"""
        # 检查是否已达到最大调用次数
        executed = state.get("executed_tools", [])
        if len(executed) >= self.max_iter:
            log(f"📊 已达到最大工具调用次数({self.max_iter})")
            return "finalize"

        # 继续选择工具
        return "select_tool"

    def _finalize(self, state: AgentState) -> AgentState:
        """整理最终结果"""
        log(f"===== 📦 整理结果 =====")

        results = state.get("tool_results", [])
        executed = state.get("executed_tools", [])

        log(f"📊 共调用{len(executed)}个工具: {executed}")

        if not results:
            state["alert_context"] = "未能获取数据"
            return state

        # 格式化结果
        parts = []
        for r in results:
            tool_name = r.get("tool", "unknown")
            if r.get("status") == "success":
                parts.append(f"【{tool_name}】\n{json.dumps(r.get('data', {}), ensure_ascii=False, indent=2)}")
            else:
                parts.append(f"【{tool_name}】\n调用失败: {r.get('error', '未知错误')}")

        answer = "\n\n".join(parts)
        log(f"✅ 完成，总结果长度: {len(answer)}字符")
        state["alert_context"] = answer
        return state

    # ==============================
    # 构建工作流
    # ==============================
    def _build_graph(self):
        wf = StateGraph(AgentState)

        wf.add_node("select_tool", self._select_tool)
        wf.add_node("execute_tool", self._execute_tool)
        wf.add_node("finalize", self._finalize)

        # 入口
        wf.add_edge(START, "select_tool")

        # select_tool 条件路由
        wf.add_conditional_edges(
            "select_tool",
            lambda s: "execute_tool" if s.get("current_tool") else "finalize",
            {"execute_tool": "execute_tool", "finalize": "finalize"}
        )

        # execute_tool 后路由回 select_tool 或 finalize
        wf.add_conditional_edges(
            "execute_tool",
            self._route_after_execute,
            {"select_tool": "select_tool", "finalize": "finalize"}
        )

        wf.add_edge("finalize", END)

        return wf.compile()

    def run(self, state: AgentState) -> AgentState:
        return self.graph.invoke(state)
