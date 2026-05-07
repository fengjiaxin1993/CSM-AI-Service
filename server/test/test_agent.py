import json
import requests
from typing import TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END


# ==============================
# 1. 智能体状态
# ==============================
class AgentState(TypedDict):
    query: str
    # 当前要执行的工具
    current_tool: str | None
    current_params: dict
    # 已执行的工具结果
    tool_results: list[dict]
    # 已调用的工具名称列表（用于避免重复）
    executed_tools: list[str]
    final_answer: str | None


# ==============================
# 2. 告警智能体
# ==============================
def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class AlarmAgent:
    def __init__(self, config_path="config.json"):
        self.config = load_config(config_path)
        self.tools = self._build_tools()
        self.llm = ChatOpenAI(
            api_key="sk-445d4654ee8e4067b447172154f0a273",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen3-32b",
            extra_body={"enable_thinking": False},
            temperature=0
        )
        self.graph = self._build_graph()

    def _build_tools(self):
        """构建工具函数字典"""
        tool_funcs = {}
        for tool in self.config["tools"]:
            name = tool["tool_name"]
            tool_funcs[name] = {
                "func": self._make_api_caller(tool),
                "desc": tool.get("description", ""),
                "params": tool.get("parameters", [])
            }
        return tool_funcs

    def _make_api_caller(self, tool_config):
        """创建API调用函数"""
        def caller(**kwargs):
            try:
                url = tool_config["url"].format(**kwargs)
                method = tool_config["method"].upper()
                headers = {"Content-Type": "application/json"}
                
                if method == "GET":
                    res = requests.get(url, headers=headers, timeout=10)
                else:
                    res = requests.post(url, json=kwargs, headers=headers, timeout=10)
                
                return {
                    "tool": tool_config["tool_name"],
                    "status": "success" if res.status_code == 200 else "error",
                    "data": res.json() if res.text else {},
                    "raw": res.text
                }
            except Exception as e:
                return {"tool": tool_config["tool_name"], "status": "error", "error": str(e)}
        return caller

    def _build_tool_descriptions(self) -> str:
        """构建工具描述文本，包含参数类型"""
        lines = []
        for name, info in self.tools.items():
            lines.append(f"- {name}: {info['desc']}")
            lines.append(f"  参数:")
            for p in info["params"]:
                param_type = p.get("type", "string")
                required = "必填" if p.get("required", True) else "可选"
                desc = p.get("description", "")
                lines.append(f"    - {p['name']}: 类型={param_type}, {required}, 说明={desc}")
        return "\n".join(lines)

    # ==============================
    # 节点函数
    # ==============================
    def _select_tool(self, state: AgentState):
        """
        选择工具 - 基于已有结果，决定是否需要调用更多工具
        """
        print(f"\n[🔎 运行日志] ===== 🔧 工具选择 =====")
        
        tools_desc = self._build_tool_descriptions()
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

        print(f"🤖 正在分析... 已调用{len(executed)}个工具")
        
        # 调用LLM
        response = self.llm.invoke([HumanMessage(content=prompt)]).content.strip()
        print(f"📤 LLM响应: {response[:300]}...")
        
        # 解析JSON
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(response[start:end+1])
                tool_name = data.get("tool_name")
                params = data.get("parameters", {})
                need_more = data.get("need_more", False)
                reason = data.get("reason", "")
                
                # 检查是否重复调用
                if tool_name and tool_name in executed:
                    print(f"⚠️ 工具 {tool_name} 已调用过，跳过")
                    return {
                        "query": state["query"],
                        "current_tool": None,
                        "current_params": {},
                        "tool_results": results,
                        "executed_tools": executed,
                        "final_answer": None
                    }
                
                if tool_name and tool_name in self.tools:
                    print(f"✅ 选择工具: {tool_name}, need_more={need_more}")
                    if reason:
                        print(f"   原因: {reason}")
                    return {
                        "query": state["query"],
                        "current_tool": tool_name,
                        "current_params": params,
                        "tool_results": results,
                        "executed_tools": executed,
                        "final_answer": None
                    }
        except Exception as e:
            print(f"❌ 解析失败: {e}")
        
        print("ℹ️ 不需要更多工具")
        return {
            "query": state["query"],
            "current_tool": None,
            "current_params": {},
            "tool_results": results,
            "executed_tools": executed,
            "final_answer": None
        }

    def _execute_tool(self, state: AgentState):
        """执行工具"""
        tool_name = state.get("current_tool")
        if not tool_name or tool_name not in self.tools:
            return state
        
        print(f"\n[🔎 运行日志] ===== ⚙️ 执行工具 =====")
        print(f"🔨 执行: {tool_name}")
        
        params = state.get("current_params", {})
        
        # 执行API调用
        result = self.tools[tool_name]["func"](**params)
        
        # 打印结果
        result_str = json.dumps(result, ensure_ascii=False)
        if len(result_str) > 300:
            print(f"📄 结果: {result_str[:300]}...")
        else:
            print(f"📄 结果: {result_str}")
        
        # 更新结果列表
        results = state.get("tool_results", [])
        results.append(result)
        
        # 更新已执行工具列表
        executed = state.get("executed_tools", [])
        executed.append(tool_name)
        
        return {
            "query": state["query"],
            "current_tool": None,  # 清空当前工具
            "current_params": {},
            "tool_results": results,
            "executed_tools": executed,
            "final_answer": None
        }

    def _route_after_execute(self, state: AgentState) -> Literal["select_tool", "finalize"]:
        """路由：执行工具后，判断是否需要继续选择工具"""
        # 检查是否已达到最大调用次数
        executed = state.get("executed_tools", [])
        if len(executed) >= 5:  # 最多调用5个工具
            print(f"\n[🔎 运行日志] 📊 已达到最大工具调用次数(5)")
            return "finalize"
        
        # 继续选择工具
        return "select_tool"

    def _finalize(self, state: AgentState):
        """整理最终结果"""
        print(f"\n[🔎 运行日志] ===== 📦 整理结果 =====")
        
        results = state.get("tool_results", [])
        executed = state.get("executed_tools", [])
        
        print(f"📊 共调用{len(executed)}个工具: {executed}")
        
        if not results:
            return {"final_answer": "未能获取数据"}
        
        # 格式化结果
        parts = []
        for r in results:
            tool_name = r.get("tool", "unknown")
            if r.get("status") == "success":
                parts.append(f"【{tool_name}】\n{json.dumps(r.get('data', {}), ensure_ascii=False, indent=2)}")
            else:
                parts.append(f"【{tool_name}】\n调用失败: {r.get('error', '未知错误')}")
        
        answer = "\n\n".join(parts)
        print(f"✅ 完成，总结果长度: {len(answer)}字符")
        
        return {"final_answer": answer}

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

    def run(self, query: str):
        """运行智能体"""
        print(f"\n{'='*60}")
        print(f"🚀 开始处理: {query}")
        
        result = self.graph.invoke({
            "query": query,
            "current_tool": None,
            "current_params": {},
            "tool_results": [],
            "executed_tools": [],
            "final_answer": None
        })
        
        return result.get("final_answer", "处理失败")


# ==============================
# 3. 配置示例
# ==============================
CONFIG_EXAMPLE = {
    "tools": [
        {
            "tool_name": "get_alert_overview",
            "description": "获取告警概览统计，包括告警总数、紧急告警数、重要告警数等",
            "method": "POST",
            "url": "http://127.0.0.1:7862/tools/alert/overview",
            "parameters": [
                {"name": "start_date", "type": "string", "required": True, "description": "开始日期，格式YYYY-MM-DD"},
                {"name": "end_date", "type": "string", "required": True, "description": "结束日期，格式YYYY-MM-DD"}
            ]
        },
        {
            "tool_name": "get_alert_trend",
            "description": "获取告警趋势数据，返回每日告警数量变化趋势",
            "method": "POST",
            "url": "http://127.0.0.1:7862/tools/alert/trend",
            "parameters": [
                {"name": "start_date", "type": "string", "required": True},
                {"name": "end_date", "type": "string", "required": True}
            ]
        },
        {
            "tool_name": "get_alert_type_dist",
            "description": "获取指定时间范围告警类型分布统计",
            "method": "POST",
            "url": "http://127.0.0.1:7862/tools/alert/type-dist",
            "parameters": [
                {"name": "start_date", "type": "string", "required": True},
                {"name": "end_date", "type": "string", "required": True}
            ]
        },
        {
            "tool_name": "get_institution_ranking",
            "description": "获取指定时间范围各机构/区域告警数量排行",
            "method": "POST",
            "url": "http://127.0.0.1:7862/tools/alert/institution-ranking",
            "parameters": [
                {"name": "start_date", "type": "string", "required": True},
                {"name": "end_date", "type": "string", "required": True}
            ]
        }
    ]
}


# ==============================
# 4. 使用示例
# ==============================
if __name__ == "__main__":
    # 创建配置
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(CONFIG_EXAMPLE, f, ensure_ascii=False, indent=2)
    
    agent = AlarmAgent()
    result = agent.run("最近7天告警情况如何，包括概览、趋势和类型分布")
    print("\n" + "=" * 60)
    print("最终结果:")
    print(result)
