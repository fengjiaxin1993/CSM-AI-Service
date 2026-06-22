# CSM-AI-Service

**ICDO 智能问答助手服务** — 面向电力行业的大模型 AI 应用后端，基于 LangChain + LangGraph + FAISS 构建，提供知识库 RAG 问答、告警处置研判、PDF/Word 文档智能解析、多智能体对话等能力。

---

## 目录

- [项目概述](#项目概述)
- [系统架构](#系统架构)
- [核心功能模块](#核心功能模块)
- [技术路线](#技术路线)
- [实现原理](#实现原理)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [API 接口一览](#api-接口一览)
- [测试](#测试)
- [部署说明](#部署说明)

---

## 项目概述

CSM-AI-Service 是为电力行业定制的 AI 智能服务平台，核心解决以下问题：

1. **知识库问答**：将电力行业规章制度、技术文档构建为向量知识库，通过 RAG 实现精准问答
2. **告警处置研判**：自动解析告警处置报告（Word/PDF），提取结构化信息，结合 LLM 智能审核合规性
3. **多智能体协作**：基于 LangGraph 构建多路由智能体，根据用户意图自动调度告警查询、知识库检索或通用对话
4. **文档智能解析**：从等保测评报告 PDF 中自动提取安全表、等保信息、分项表等结构化数据
5. **检修票关联**：根据检修对象和内容，智能关联相关设备

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     客户端 (前端/三方系统)                  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI 路由层 (7组API)                  │
│  /chat  /chat_manager  /knowledge_base  /warning        │
│  /warning_handle  /parse_pdf  /ticket                    │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                   对话引擎层 (Conversation)               │
│  ┌──────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ Chat │ │ MemChat  │ │ KB Chat  │ │ Agent Chat     │  │
│  └──────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────────┐ ┌────────────────┐                    │
│  │ SimilarChat  │ │ FileChat       │                    │
│  └──────────────┘ └────────────────┘                    │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                 LangChain / LangGraph 编排层              │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ LLM 工厂   │  │ Embedding   │  │ LangGraph       │   │
│  │ (OpenAI兼容)│  │ 工厂        │  │ 多智能体工作流    │   │
│  └────────────┘  └─────────────┘  └─────────────────┘   │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ TextSplitter│  │ Document    │  │ Callback        │   │
│  │ (中文优化)  │  │ Loaders     │  │ Handlers        │   │
│  └────────────┘  └─────────────┘  └─────────────────┘   │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    存储与基础设施层                        │
│  ┌──────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ FAISS│  │ SQLite   │  │ 文件系统   │  │ 模型平台    │  │
│  │向量库 │  │ (会话/KB)│  │ (文档/模板)│  │(Ollama等) │  │
│  └──────┘  └──────────┘  └──────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 核心功能模块

### 1. 对话引擎 (`/chat`)

提供 6 种对话模式，覆盖不同场景：

| 模式 | 入口 | 说明 |
|------|------|------|
| 基础对话 | `/chat/chat` | 纯 LLM 对话，无上下文记忆 |
| 记忆对话 | `/chat/mem_chat` | 基于 SQLite 存储历史，支持多轮上下文 |
| 相似记忆对话 | `/chat/similar_mem_chat` | 基于 FAISS 用户向量，检索相似历史问答 |
| 知识库对话 | `/chat/kb_chat` | RAG 问答，从知识库检索相关文档后生成回答 |
| 文件对话 | `/chat/unified_chat` + file_id | 上传文件后基于文件内容问答 |
| 智能体对话 | `/chat/chat_agent` | LangGraph 多路由智能体，自动意图识别 |
| 统一对话 | `/chat/unified_chat` | 统一入口，可选知识库/文件/普通模式 |

**流式输出**：所有对话均支持 SSE 流式输出，兼容 OpenAI API 格式。

### 2. 智能体系统 (`/chat/chat_agent`)

基于 LangGraph 构建的多路由智能体，架构如下：

```
START → Supervisor(意图识别) ──┬── alert → TimeParse → AlertAgent → END
                               ├── rag   → RAG_Agent → END
                               └── llm   → LLM_Agent → END
```

- **Supervisor 节点**：LLM 意图识别，将问题路由到 alert / rag / llm 三条链路
- **Alert 路径**：先解析时间语义（"最近7天"→ 日期范围），再由 AlertAgent 循环调用配置化的 HTTP 工具获取告警数据，最后由 LLM 润色输出
- **RAG 路径**：从默认知识库检索相关文档，基于 RAG 模板生成回答
- **LLM 路径**：直接调用 LLM 通用对话

AlertAgent 内部也是一个 LangGraph 子工作流：

```
START → SelectTool ──┬──(有工具)── ExecuteTool → SelectTool (循环，最多 max_iter 次)
                     └──(无工具)── Finalize → END
```

工具列表通过 `agent_tools_settings.yaml` 配置，支持动态扩展。

### 3. 知识库管理 (`/knowledge_base`)

- **向量数据库**：FAISS（CPU），三类缓存池：知识库池 / 临时文件池 / 用户记忆池
- **文档加载**：支持 PDF、Word、Excel、CSV、Markdown、TXT、JPG(OCR) 等 7 种格式
- **文本分割**：内置中文优化分割器 `ChineseRecursiveTextSplitter`，支持 `MarkdownHeaderTextSplitter`
- **向量化流程**：文件上传 → DocumentLoader 加载 → TextSplitter 分割 → Embedding 向量化 → FAISS 存储
- **CRUD 操作**：创建/删除知识库、上传/删除/更新文档、搜索、重建向量库

### 4. 告警处置研判 (`/warning`)

面向电力行业告警处置报告的智能审核流程：

1. **报告上传** → 保存为临时文件
2. **信息提取** → LLM 从 Word/PDF 中提取结构化字段（报告标题、告警信息、设备名称、处置过程、原因分析等）
3. **RAG 增强** → 从告警知识库检索同类案例作为参考
4. **智能研判** → LLM 按六大维度（内容完整性、处置合规性、原因分析有效性、整改闭环、四不放过原则、历史一致性）生成审核结论
5. **结果输出** → 通过/驳回/需人工复核 + 详细审核意见

**整改通知单生成**：基于 `docxtpl` 模板引擎，将研判结果填充到 `warning_notice_template.docx` 模板中生成 Word 文档。

### 5. PDF 智能解析 (`/parse_pdf`)

专门针对电力行业等保测评报告的结构化提取：

- `extract_safe_table`：提取安全表
- `extract_dbcp_info`：提取等保信息
- `extract_safe_split_table`：提取安全分项表

基于 PyMuPDF 解析 PDF，结合 LLM 进行表格结构识别和字段提取。

### 6. 合同审计 (`/ocr_contract`)

面向合同文档的 OCR 识别 + 智能审计全流程：

1. **合同上传** → 保存文件
2. **PDF 解析** → 先尝试文本 PDF 解析（`text_pdf_parser`），若提取文字不足则自动调用 OCR 服务（可配置开关和阈值）
3. **结果缓存** → 解析结果持久化到文件缓存，避免重复解析
4. **规则审计** → 基于配置的审计规则，通过 LangGraph 工作流逐条审计合同合规性
5. **报告生成** → 输出每条规则的合规结论、推理过程和最终审计报告

```
上传合同 → task_queue 异步消费 → OCR/文本解析 → 缓存结果 → LangGraph 审计 → 保存审计结果
```

核心模块：
- `text_pdf_parser.py`：基于 PyMuPDF 的文本 PDF 解析，支持目录识别、标题分级、表格提取、水印去除、页码去除
- `pdf_extract_service.py`：PDF 解析调度，先文本后 OCR 的两级解析策略
- `task_queue.py`：异步任务队列，单线程消费，支持 OCR → 审计两阶段编排
- `audit/audit_graph.py`：LangGraph 审计工作流
- `tools/locate_tools.py`：文本定位，按标点切分关键词匹配

### 7. 会话管理 (`/chat_manager`)

- 会话 CRUD（创建/保存/删除）
- 会话消息查询（分页）
- 收藏/取消收藏
- 推荐问题生成

### 8. 平台告警接收 (`/warning_handle`)

模拟安全平台告警推送接口，接收告警原始数据并入库。

### 9. 检修票关联 (`/ticket`)

根据检修对象、受影响对象、工作内容，通过 LLM 智能关联相关设备，区分变电站/非变电站场景。

---

## 技术路线

| 领域 | 技术选型 | 说明 |
|------|---------|------|
| Web 框架 | FastAPI + Uvicorn | 异步高性能，自动 OpenAPI 文档 |
| LLM 编排 | LangChain 1.x | Chain / Prompt / Callback 体系 |
| 多智能体 | LangGraph | 声明式状态图，支持条件路由与循环 |
| 向量数据库 | FAISS (CPU) | 轻量级本地向量存储，适合低配环境 |
| LLM 接口 | OpenAI 兼容协议 | 支持 Ollama / OpenAI / 阿里云百练等 |
| Embedding | bge-small-zh-v1.5 | 中文优化 Embedding 模型 |
| 文档解析 | PyMuPDF / docx2txt / Unstructured | 多格式文档加载 |
| 数据库 | SQLite + SQLAlchemy | 轻量级，无需额外数据库服务 |
| 流式输出 | SSE (sse-starlette) | 兼容 OpenAI API 流式格式 |
| 配置管理 | Pydantic + YAML | 5 组配置文件，支持热重载 |
| 中文优化 | ChineseRecursiveTextSplitter | 递归中文字符级分割，避免截断 |

---

## 实现原理

### RAG 问答流程

```
用户提问 → Embedding 向量化 → FAISS 相似度检索 Top-K →
  拼接上下文 + Prompt 模板 → LLM 生成回答 → 流式/非流式输出
```

核心代码路径：`kb_chat.py` → `search_docs()` → FAISS 检索 → Prompt 组装 → LLM 推理

### 多智能体工作流

基于 LangGraph 的 `StateGraph` 声明式工作流：

1. **状态定义**：`AgentState` TypedDict 包含 query、route、时间信息、工具结果、上下文等
2. **Supervisor 路由**：LLM 单 token 分类（alert / rag / llm）
3. **条件边**：`add_conditional_edges` 根据状态字段动态路由
4. **工具循环**：AlertAgent 内部 select_tool → execute_tool → 判断是否继续，最多迭代 `max_iter` 次
5. **答案生成**：工作流结束后，根据 route 类型选择不同 Prompt 模板生成最终答案

### 告警研判流程

```
上传 Word/PDF → 临时文件保存 → LLM 提取结构化 JSON →
  标准 JSON 校验 → 告警知识库 RAG 检索同类案例 →
  LLM 六维度审核 → 结构化审核结果 → (可选) 生成整改通知单
```

### 合同审计流程

```
上传合同 PDF → task_queue 异步消费
  → 阶段一(OCR)：text_pdf_parser 文本解析
    → 文字充足(≥阈值) → 直接使用文本解析结果
    → 文字不足 + OCR_ENABLED → 调用 OCR 服务 → 成功/失败回退
    → 文字不足 + OCR_DISABLED → 使用文本解析结果
  → 结果缓存到文件
  → 阶段二(审计)：加载审计规则 → LangGraph 逐条审计 → 保存审计结果
```

**PDF 解析两级策略**：
1. **第一级：文本 PDF 解析**（`text_pdf_parser`）：基于 PyMuPDF 直接提取文本，速度快、无外部依赖
2. **第二级：OCR 服务**（条件触发）：当文本解析提取的文字数量低于 `OCR_MIN_TEXT_LENGTH` 且 `OCR_ENABLED=true` 时，调用外部 OCR 服务解析扫描件

### 向量缓存机制

三类 FAISS 缓存池，基于 `ThreadSafeObject` 线程安全抽象：

| 池类型 | 用途 | 默认缓存数 |
|--------|------|-----------|
| `kb_faiss_pool` | 知识库向量 | 1 |
| `memo_faiss_pool` | 临时文件向量 | 10 |
| `user_faiss_pool` | 用户记忆向量 | 3 |

LRU 策略自动淘汰，避免内存溢出。

### 中文文本分割优化

`ChineseRecursiveTextSplitter`：递归按中文字符分割，优先按段落 → 句号 → 逗号 → 字符级切割，避免在词语中间截断，保证语义完整性。

---

## 项目结构

```
csm_ai_service/
├── cli.py                              # CLI 入口 (click: init/start/kb)
├── startup.py                          # API 服务启动
├── settings.py                         # 全局配置 (5组YAML)
├── pydantic_settings_file.py           # YAML 配置基类
├── utils.py                            # 通用工具
│
├── data/                               # 运行时数据
│   ├── knowledge_base/                 # 知识库 (content + vector_store + info.db)
│   ├── temp/                           # 文件对话临时目录
│   ├── template_file/                  # 整改通知单模板
│   ├── user/                           # 用户向量数据
│   └── warning_notice/                 # 生成的整改通知单
│
└── server/
    ├── utils.py                        # LLM/Embedding 工厂、响应模型
    ├── api_server/                     # API 路由层
    │   ├── server_app.py               # FastAPI 应用 & 路由注册
    │   ├── api_schemas.py              # OpenAI 兼容 Schema
    │   ├── chat_routes.py              # /chat/*
    │   ├── kb_routes.py                # /knowledge_base/*
    │   ├── warning_routes.py           # /warning/*
    │   ├── platform_warning_routes.py  # /warning_handle/*
    │   ├── pdf_extract_routes.py       # /parse_pdf/*
    │   ├── ocr_routes.py               # /ocr_contract/* (合同OCR)
    │   ├── contract_routes.py          # 合同管理
    │   ├── task_routes.py              # 审计任务管理
    │   ├── audit_rule_routes.py        # 审计规则管理
    │   ├── audit_result_routes.py      # 审计结果查询
    │   ├── tickets_routes.py           # /ticket/*
    │   └── chat_manager_routes.py      # /chat_manager/*
    │
    ├── conversation/                   # 对话核心逻辑
    │   ├── chat/                       # 各对话模式实现
    │   │   ├── chat.py                 # 基础对话
    │   │   ├── mem_chat.py             # 记忆对话
    │   │   ├── similar_mem_chat.py     # 相似记忆对话
    │   │   ├── kb_chat.py             # 知识库 RAG 对话
    │   │   ├── file_chat.py           # 文件对话 + 临时文件上传
    │   │   └── utils.py               # History 消息模型
    │   │
    │   ├── chat_agent/                 # LangGraph 智能体
    │   │   ├── agent_chat.py          # 智能体对话入口
    │   │   ├── agentStatus.py         # AgentState 定义
    │   │   ├── alert_agent.py         # 告警工具调用 Agent
    │   │   └── node.py                # 工作流节点 (supervisor/time_parse/rag/llm/alert)
    │   │
    │   ├── chat_manager/              # 会话管理
    │   │   └── chat_manager.py        # CRUD + 推荐问题
    │   │
    │   ├── callback_handler/          # LLM 回调
    │   │   ├── message_callback_handler.py  # 消息持久化
    │   │   └── user_callback_handler.py      # 用户向量持久化
    │   │
    │   ├── file_rag/                  # 文件 RAG 工具
    │   │   ├── retrievers/            # 向量检索服务
    │   │   ├── document_loaders/       # 自定义文档加载器 (RapidOCR等)
    │   │   └── text_splitter/         # 自定义分割器 (中文优化)
    │   │
    │   └── knowledge_base/            # 知识库核心模块
    │       ├── kb_api.py              # 知识库 CRUD
    │       ├── kb_doc_api.py          # 文档管理 (上传/删除/搜索)
    │       ├── utils.py              # KnowledgeFile、加载器/分割器映射
    │       ├── migrate.py            # 数据库迁移
    │       ├── kb_cache/             # FAISS 缓存池
    │       │   ├── base.py           # CachePool 线程安全抽象
    │       │   └── faiss_cache.py    # 三类 FAISS 缓存池
    │       └── kb_service/           # 知识库服务
    │           ├── base.py           # KBService 抽象 + Factory
    │           └── faiss_service.py  # FAISS 实现
    │
    ├── csm_analyze/                   # 行业分析模块
    │   └── warning_analysis/          # 告警研判
    │       ├── report_analyze.py      # 报告分析 (提取+研判)
    │       ├── gen_notice.py          # 整改通知单生成
    │       └── pdf_extract.py         # PDF 结构化提取
    │
    ├── protection_audit/              # 合同审计模块
    │   ├── text_pdf_parser.py         # 文本 PDF 解析器 (PyMuPDF)
    │   ├── pdf_extract_service.py     # PDF 解析调度 (文本优先→OCR)
    │   ├── task_queue.py              # 异步任务队列 (OCR→审计)
    │   ├── audit/                     # 审计工作流
    │   │   ├── audit_graph.py         # LangGraph 审计图
    │   │   ├── extract_audit.py       # 审计提取
    │   │   └── model.py              # 审计数据模型
    │   └── tools/                     # 审计工具
    │       ├── file_tools.py          # 文件缓存/存储
    │       ├── locate_tools.py        # 文本定位 (关键词切分匹配)
    │       ├── ocr_tools.py           # OCR 结果处理
    │       └── pdf_tools.py           # PDF 工具
    │
    └── db/                            # 数据库层
        ├── models/                    # SQLAlchemy 模型
        └── repository/                # 数据访问层
            ├── conversation_repository.py
            ├── message_repository.py
            └── user_message_repository.py
```

---

## 快速开始

### 环境要求

- Python 3.9+
- LLM 服务（推荐 [Ollama](https://ollama.ai) 部署本地模型）

### 安装

```bash
# 克隆项目
git clone https://github.com/xxx/CSM-AI-Service.git
cd CSM-AI-Service

# 安装依赖
pip install -r requirements.txt

# 或使用 conda（推荐国产系统凝思/麒麟）
conda env create -f conda-environment.yml
conda activate chatchat
```

### 启动

```bash
# 1. 初始化（生成配置文件 + 数据目录 + 数据库表）
python -m csm_ai_service.cli init

# 2. 修改模型配置
#    编辑 model_settings.yaml，确认 LLM 和 Embedding 模型地址

# 3. 构建知识库向量（可选，data/knowledge_base/samples/ 中放入文档）
python -m csm_ai_service.cli kb -r

# 4. 启动 API 服务
python -m csm_ai_service.cli start
```

服务默认启动在 `http://127.0.0.1:7861`，访问 `/docs` 查看 Swagger 文档。

---

## 配置说明

项目通过 5 个 YAML 配置文件管理，初始化时自动生成：

| 配置文件 | 对应类 | 说明 |
|---------|--------|------|
| `basic_settings.yaml` | BasicSettings | 服务地址、数据目录、跨域、日志、OCR 开关/地址/阈值等 |
| `kb_settings.yaml` | KBSettings | 知识库参数（分块大小、重叠、Top-K、相似度阈值） |
| `model_settings.yaml` | ApiModelSettings | LLM/Embedding 模型、平台地址、温度等 |
| `agent_tools_settings.yaml` | AgentToolsSettings | 告警智能体工具列表（URL、参数、描述） |
| `prompt_settings.yaml` | PromptSettings | 各场景 Prompt 模板（RAG/Agent/Warning） |

**`basic_settings.yaml` 中 OCR 相关配置**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `OCR_ENABLED` | `true` | 是否启用 OCR 服务，关闭后仅使用文本 PDF 解析 |
| `OCR_SERVICE_URL` | `http://127.0.0.1:7840` | OCR 服务地址 |
| `OCR_MIN_TEXT_LENGTH` | `100` | 文本解析后文字数量低于此阈值时判定为扫描件，需调用 OCR |

所有配置支持热重载，修改 YAML 后自动生效（部分需重启）。
OCR服务一定要启动， 参考OCR-SERVICE这个项目

---

## API 接口一览

### `/chat` — 对话接口

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/chat/chat` | 基础/流式对话 |
| POST | `/chat/mem_chat` | 记忆对话 |
| POST | `/chat/similar_mem_chat` | 相似记忆对话 |
| POST | `/chat/kb_chat` | 知识库对话 |
| POST | `/chat/chat_agent` | 智能体对话 |
| POST | `/chat/unified_chat` | 统一对话（支持文件ID） |

### `/chat_manager` — 会话管理

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/chat_manager/possible_questions` | 推荐问题 |
| POST | `/chat_manager/conversation/save_conversation` | 保存会话 |
| POST | `/chat_manager/conversations` | 会话列表 |
| POST | `/chat_manager/conversation/messages` | 会话消息 |
| POST | `/chat_manager/conversation/toggle_favorite` | 收藏/取消 |
| POST | `/chat_manager/conversation/delete` | 删除会话 |

### `/knowledge_base` — 知识库

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/knowledge_base/list_knowledge_bases` | 列出知识库 |
| POST | `/knowledge_base/create_knowledge_base` | 创建知识库 |
| GET | `/knowledge_base/list_files` | 列出文件 |
| POST | `/knowledge_base/upload_docs` | 上传文档 |
| POST | `/knowledge_base/delete_docs` | 删除文档 |
| POST | `/knowledge_base/search_docs` | 搜索文档 |
| POST | `/knowledge_base/upload_temp_docs` | 上传临时文档 |
| POST | `/knowledge_base/search_temp_docs` | 搜索临时文档 |
| POST | `/knowledge_base/update_info` | 更新知识库信息 |
| POST | `/knowledge_base/update_docs` | 更新文档 |
| POST | `/knowledge_base/recreate_vector_store` | 重建向量库 |
| POST | `/knowledge_base/delete_knowledge_base` | 删除知识库 |

### `/warning` — 告警处置

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/warning/analyze` | 上传报告 + 智能研判 |
| POST | `/warning/generate_notice_doc` | 生成整改通知单 |
| POST | `/warning/save_warning_report` | 保存报告到知识库 |
| POST | `/warning/delete_warning_report` | 删除报告 |

### `/parse_pdf` — PDF 解析

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/parse_pdf/extract_safe_table` | 提取安全表 |
| POST | `/parse_pdf/extract_dbcp_info` | 提取等保信息 |
| POST | `/parse_pdf/extract_safe_split_table` | 提取安全分项表 |

### `/warning_handle` — 平台告警

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/warning_handle/warning` | 接收平台告警数据 |

### `/ocr_contract` — 合同 OCR 与审计

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/ocr_contract/upload` | 上传合同文件 |
| POST | `/ocr_contract/parse` | 触发 OCR 解析 |
| GET  | `/ocr_contract/status/{task_id}` | 查询解析/审计状态 |
| GET  | `/ocr_contract/result/{task_id}` | 获取审计结果 |

### 合同管理

| 方法 | 路由 | 说明 |
|------|------|------|
| GET  | `/contracts` | 合同列表 |
| GET  | `/contracts/{id}` | 合同详情 |

### 审计任务

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建审计任务 |
| GET  | `/tasks` | 任务列表 |
| GET  | `/tasks/{id}` | 任务详情 |

### 审计规则

| 方法 | 路由 | 说明 |
|------|------|------|
| GET  | `/audit_rules` | 规则列表 |
| POST | `/audit_rules` | 创建规则 |
| PUT  | `/audit_rules/{id}` | 更新规则 |
| DELETE | `/audit_rules/{id}` | 删除规则 |

### 审计结果

| 方法 | 路由 | 说明 |
|------|------|------|
| GET  | `/audit_results` | 结果列表 |
| GET  | `/audit_results/{id}` | 结果详情 |

### `/ticket` — 检修票

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/ticket/associate_device` | 关联设备 |

---

## 测试

详见 [测试说明文档](src/csm_ai_service/test_api/pytest/README_TEST.md)

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行全部测试
cd src/csm_ai_service/test_api/pytest
pytest -s -v

# 运行单个 Route
pytest test_chat_routes.py -s -v

# 运行单个测试方法
pytest test_chat_routes.py::test_kb_chat -s -v
```

---

## 1.开发说明
### 1.1 源码启动

```bash
cd CSM-AI-Service
cd src/csm_ai_service
python cli.py init
python cli.py kb -r
python cli.py start
```

### 1.2 pip可编辑安装（不依赖poetry）启动

```bash
cd CSM-AI-Service
# 可编辑模式安装项目（代码修改实时生效）
pip install -e .
# 安装后同样可以直接使用 CLI 命令：
# 初始化
icdo init
# 生成向量库
icdo kb -r
# 启动服务
icdo start
```

## 2.构建wheel包说明(通过poetry)

```bash
cd CSM-AI-Service
poetry build
# 安装包在dist目录下
```

## 3. conda 部署

```bash
conda create -n ICDO-RNV python=3.11
conda activate ICDO-RNV
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
or
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 安装icdo
pip install dist/icdo-1.2.0.tar.gz
```
## 4. 启动项目
```bash
# 初始化
icdo init
# 生成向量库
icdo kb -r
# 启动服务
icdo start
```