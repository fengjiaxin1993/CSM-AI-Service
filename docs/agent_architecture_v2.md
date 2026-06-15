# CSM-AI-Service 智能体架构 V2.0

## 架构演进：从单链路由到多智能体协作

### 一、V1.0 vs V2.0 对比

| 特性 | V1.0 传统架构 | V2.0 增强架构 |
|------|--------------|---------------|
| **路由方式** | 单链互斥路由 (supervisor三选一) | 智能规划器 (Planner) 任务分解 |
| **记忆能力** | 仅最近10条对话 | L1-L3分层记忆系统 |
| **Agent协作** | 单个Agent执行 | 多Agent并行/串行协作 |
| **复合问题** | 不支持 | 自动分解为子任务 |
| **结果质量** | 单源信息 | 多源融合+反思验证 |
| **知识积累** | 无 | 自动沉淀长期记忆 |

---

### 二、V2.0 核心架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│                    Web / API / 移动端                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  START → ┌──────────────┐                                      │
│          │ Memory       │  L1: 会话记忆 (最近10条对话)         │
│          │ Retrieve     │  L2: 用户画像 (偏好区域、角色)       │
│          │ Node         │  L3: 长期知识 (FAISS向量库)          │
│          └──────────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      规划层 (Planner)                           │
│  输入: 用户问题 + 记忆上下文                                     │
│  输出: 子任务列表 [{agent_type, sub_query, dependencies}...]   │
│                                                                 │
│  示例: "华东告警最多的设备+处置规范"                             │
│  → task1: alert Agent → 查询华东告警设备排行                     │
│  → task2: rag Agent   → 检索告警处置规范 (依赖task1)            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    调度层 (Dispatcher)                          │
│  循环执行子任务，支持:                                           │
│  - 串行执行 (有依赖关系的任务)                                  │
│  - 结果收集 (每个Agent的执行结果)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   融合层 (Fusion)                               │
│  多Agent结果合并为统一上下文                                     │
│  【告警数据分析】+ 【知识库检索结果】→ 融合上下文                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  反思层 (Reflection)                            │
│  自我验证：信息是否充足？置信度是否达标？                         │
│  - 通过 → 进入答案生成                                          │
│  - 不足 → 返回调度器补充查询 (最多2次)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 答案生成 + 记忆存储                              │
│  差异化Prompt：                                                 │
│  - multi模式: 基于融合上下文生成综合答案                         │
│  - alert模式: 电力专家人设润色                                   │
│  - rag模式: 严格基于检索结果，禁止编造                           │
│  - llm模式: 自然对话风格                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

### 三、核心组件说明

#### 1. 分层记忆系统 (HierarchicalMemory)

**文件**: `server/chat_agent/memory/`

| 层级 | 存储位置 | 内容 | 用途 |
|------|----------|------|------|
| L1 | SQLite conversation表 | 最近10条对话 | 会话上下文 |
| L2 | SQLite user_profiles表 | 用户偏好区域、角色、常问问题 | 个性化 |
| L3 | FAISS agent_memory库 | 重要发现、告警规律、历史摘要 | 知识积累 |

**关键接口**:
```python
# 检索记忆
memory_context = memory.build_memory_context(conversation_id, query)

# 存储记忆
memory.store_long_term_memory(content, metadata)
memory.update_user_profile(conversation_id, profile)
```

#### 2. 智能任务规划器 (Planner)

**文件**: `server/chat_agent/node.py:planner_node`

**职责**:
- 分析用户问题复杂度
- 判断是否需要多任务分解
- 生成带依赖关系的子任务列表

**示例**:
```python
# 输入: "最近7天华东告警最多的设备类型是什么？相关处置规范有哪些？"

# 输出任务计划:
[
    {
        "task_id": "task_1",
        "agent_type": "alert",
        "sub_query": "最近7天华东区域告警最多的设备类型",
        "dependencies": [],
        "priority": 0
    },
    {
        "task_id": "task_2",
        "agent_type": "rag",
        "sub_query": "电力监控设备告警处置规范",
        "dependencies": ["task_1"],  # 可基于task1结果精确检索
        "priority": 1
    }
]
```

#### 3. 动态任务调度器 (Dispatcher)

**文件**: `server/chat_agent/node.py:dispatcher_node`

**执行逻辑**:
```python
def dispatcher_node(state: AgentState) -> AgentState:
    current_task = task_plan[current_task_index]
    
    if agent_type == "alert":
        # 执行时间解析 → AlertAgent → 保存结果
        state["agent_results"]["alert"] = result
    
    elif agent_type == "rag":
        # 执行RAG检索 → 保存结果
        state["agent_results"]["rag"] = result
    
    # 移动到下一个任务
    current_task_index += 1
```

#### 4. 结果融合引擎 (Fusion)

**文件**: `server/chat_agent/node.py:fusion_node`

**融合策略**:
```python
def fusion_node(state: AgentState) -> AgentState:
    if len(agent_results) == 1:
        # 单Agent，直接传递
        fusion_context = agent_results[agent_type]
    else:
        # 多Agent，格式化合并
        fusion_parts = []
        if "alert" in agent_results:
            fusion_parts.append(f"【告警数据分析】\n{alert_result}")
        if "rag" in agent_results:
            fusion_parts.append(f"【知识库检索结果】\n{rag_result}")
        fusion_context = "\n\n".join(fusion_parts)
```

#### 5. 反思验证器 (Reflection)

**文件**: `server/chat_agent/node.py:reflection_node`

**自我验证流程**:
1. LLM评估：信息是否完整？置信度如何？
2. 质量判断：sufficient + confidence > 0.6
3. 动态补充：如不足，返回调度器补充查询（最多2次）

---

### 四、状态定义 (AgentState)

```python
class AgentState(TypedDict):
    # 原始输入
    query: str
    conversation_id: str
    msg_id: str
    is_stream: bool
    
    # 记忆相关
    chat_history: List[dict]          # L1: 会话记忆
    user_profile: Optional[dict]      # L2: 用户画像
    memory_context: Optional[str]     # L3: 长期知识
    
    # 规划相关
    task_plan: List[dict]             # 子任务列表
    current_task_index: int           # 当前任务索引
    needs_planning: bool              # 是否需要规划
    
    # 协作相关
    agent_results: dict               # 各Agent结果 {type: result}
    fusion_context: Optional[str]     # 融合后上下文
    reflection_needed: bool           # 是否需要反思
    reflection_count: int             # 反思次数计数
    
    # 路由与执行
    route: str                        # 路由类型
    time_desc: str
    start_date: str
    end_date: str
    
    # 中间结果
    current_tool: Optional[str]
    current_params: dict
    tool_results: List[dict]
    executed_tools: List[str]
    
    # 最终结果
    rag_context: str
    alert_context: str
    final_answer: str
```

---

### 五、工作流图 (StateGraph)

```python
# 节点定义
workflow.add_node("memory_retrieve", memory_retrieve_node)  # 记忆检索
workflow.add_node("planner", planner_node)                   # 智能规划
workflow.add_node("dispatcher", dispatcher_node)             # 任务调度
workflow.add_node("fusion", fusion_node)                     # 结果融合
workflow.add_node("reflection", reflection_node)             # 反思验证
workflow.add_node("memory_store", memory_store_node)         # 记忆存储

# 边连接
START → memory_retrieve → planner → dispatcher

dispatcher ──(continue)──→ dispatcher  # 还有任务，继续调度
dispatcher ──(fusion)────→ fusion      # 任务完成，进入融合

fusion → reflection

reflection ──(dispatch)──→ dispatcher  # 需要补充，返回调度
reflection ──(generate)──→ memory_store → END
```

---

### 六、使用方式

#### API 调用

```python
# 使用增强版架构（默认）
POST /agent/chat
{
    "query": "最近7天华东告警最多的设备类型是什么？",
    "conversation_id": "user_001_session_01",
    "stream": false,
    "use_enhanced": true  # 启用 V2.0 增强架构
}

# 使用传统版架构（兼容旧版）
POST /agent/chat
{
    "query": "最近7天告警情况如何",
    "conversation_id": "user_001_session_01",
    "stream": false,
    "use_enhanced": false  # 使用 V1.0 传统架构
}
```

---

### 七、扩展指南

#### 新增一个Agent类型

1. **在 planner_node 中添加新Agent类型说明**
```python
available_agents = """
4. new_agent - 新Agent描述
"""
```

2. **在 dispatcher_node 中添加执行逻辑**
```python
elif agent_type == "new_agent":
    result = new_agent_logic(state)
    state["agent_results"]["new_agent"] = result
```

3. **在 fusion_node 中添加融合逻辑**
```python
if "new_agent" in agent_results:
    fusion_parts.append(f"【新Agent结果】\n{new_result}")
```

---

### 八、性能与可靠性

| 特性 | 实现方式 |
|------|----------|
| **并行执行** | 独立子任务可并行（当前实现为串行，可扩展） |
| **优雅降级** | 单个Agent失败不影响其他Agent结果 |
| **防循环** | reflection_count 限制最多2次反思 |
| **记忆容错** | 记忆检索失败时，Planner仍可正常工作 |
| **幂等设计** | 重复请求不会产生重复记忆 |

---

### 九、后续优化方向

1. **真正的并行执行**: 使用 asyncio.gather 并行执行无依赖关系的子任务
2. **Agent注册表**: 通过配置文件动态注册新Agent
3. **更智能的反思**: 基于置信度动态决定是否需要补充
4. **长期知识自动总结**: 定期自动总结会话并沉淀到L3
5. **用户画像自学习**: 自动从查询中提取用户偏好

---

**文档版本**: v2.0  
**更新日期**: 2026-05-09  
**作者**: AI Architecture Team
