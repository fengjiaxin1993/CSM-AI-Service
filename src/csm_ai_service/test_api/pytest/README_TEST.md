# 接口测试说明

## 前置条件

1. **启动服务**：确保 CSM-AI-Service 已在 `http://127.0.0.1:7861` 运行
2. **安装依赖**：
   ```bash
   pip install pytest pytest-asyncio httpx
   ```
3. **测试文件**：部分测试依赖真实文件，需放在 `pytest/` 目录下：

   | 文件名 | 依赖的测试 |
   |--------|-----------|
   | `《电力监控系统安全防护规定》27号令.pdf` | `test_chat_routes::test_unified_chat_with_file` |
   | `2018泉州供电公司调度自动化系统信息安全等级测评报告-S2A3G3.pdf` | `test_pdf_extract_routes` (全部) |
   | `关于110kVXX变告警说明.docx` | `test_warning_routes::test_warning_analyze`, `test_save_warning_report` |

---

## 运行所有测试

```bash
# 在项目根目录下
cd src/csm_ai_service/test_api/pytest

# 运行全部测试（-s 显示 print 输出，-v 显示详细）
pytest -s -v
```

---

## 运行单个 Route 文件

```bash
# 对话接口
pytest test_chat_routes.py -s -v

# 对话管理接口
pytest test_chat_manager_routes.py -s -v

# 知识库接口
pytest test_kb_routes.py -s -v

# PDF 解析接口
pytest test_pdf_extract_routes.py -s -v

# 告警处置报告接口
pytest test_warning_routes.py -s -v

# 平台告警接口
pytest test_platform_warning_routes.py -s -v

# 工单接口
pytest test_ticket_routes.py -s -v
```

---

## 运行单个测试方法

```bash
# 语法：pytest <文件>::<方法名> -s -v

# 例：只测试文件对话
pytest test_chat_routes.py::test_unified_chat_with_file -s -v

# 例：只测试告警分析
pytest test_warning_routes.py::test_warning_analyze -s -v

# 例：只测试PDF安全表提取
pytest test_pdf_extract_routes.py::test_extract_safe_table -s -v
```

---

## 各 Route 测试用例一览

### 1. `/chat` — 对话接口 (`test_chat_routes.py`)

| 测试方法 | 路由 | 说明 |
|---------|------|------|
| `test_chat` | POST `/chat/chat` | 基础对话（非流式） |
| `test_chat_stream` | POST `/chat/chat` | 基础对话（流式） |
| `test_mem_chat` | POST `/chat/mem_chat` | 带记忆对话 |
| `test_similar_mem_chat` | POST `/chat/similar_mem_chat` | 相似记忆对话 |
| `test_kb_chat` | POST `/chat/kb_chat` | 知识库对话 |
| `test_agent_chat` | POST `/chat/chat_agent` | Agent 对话 |
| `test_unified_chat` | POST `/chat/unified_chat` | 统一对话（无文件） |
| `test_unified_chat_with_file` | POST `/chat/unified_chat` | 统一对话（带文件），需PDF |

### 2. `/chat_manager` — 对话管理接口 (`test_chat_manager_routes.py`)

| 测试方法 | 路由 | 说明 |
|---------|------|------|
| `test_possible_questions` | POST `/chat_manager/possible_questions` | 推荐问题 |
| `test_save_conversation` | POST `/chat_manager/conversation/save_conversation` | 保存会话 |
| `test_get_conversations` | POST `/chat_manager/conversations` | 获取会话列表 |
| `test_get_conversation_messages` | POST `/chat_manager/conversation/messages` | 获取会话消息 |
| `test_toggle_favorite` | POST `/chat_manager/conversation/toggle_favorite` | 收藏/取消收藏 |
| `test_delete_conversation` | POST `/chat_manager/conversation/delete` | 删除会话 |

### 3. `/knowledge_base` — 知识库接口 (`test_kb_routes.py`)

| 测试方法 | 路由 | 说明 |
|---------|------|------|
| `test_list_kbs` | GET `/knowledge_base/list_knowledge_bases` | 列出知识库 |
| `test_create_kb` | POST `/knowledge_base/create_knowledge_base` | 创建知识库 |
| `test_list_files` | GET `/knowledge_base/list_files` | 列出文件 |
| `test_search_docs` | POST `/knowledge_base/search_docs` | 搜索文档 |
| `test_upload_docs` | POST `/knowledge_base/upload_docs` | 上传文档 |
| `test_delete_docs` | POST `/knowledge_base/delete_docs` | 删除文档 |
| `test_update_info` | POST `/knowledge_base/update_info` | 更新知识库信息 |
| `test_update_docs` | POST `/knowledge_base/update_docs` | 更新文档 |
| `test_recreate_vector_store` | POST `/knowledge_base/recreate_vector_store` | 重建向量库 |
| `test_upload_temp_docs` | POST `/knowledge_base/upload_temp_docs` | 上传临时文档 |
| `test_search_temp_docs` | POST `/knowledge_base/search_temp_docs` | 搜索临时文档 |
| `test_delete_kb` | POST `/knowledge_base/delete_knowledge_base` | 删除知识库 |

### 4. `/parse_pdf` — PDF解析接口 (`test_pdf_extract_routes.py`)

| 测试方法 | 路由 | 说明 | 需文件 |
|---------|------|------|--------|
| `test_extract_safe_table` | POST `/parse_pdf/extract_safe_table` | 提取安全表 | 是 |
| `test_extract_dbcp_info` | POST `/parse_pdf/extract_dbcp_info` | 提取等保信息 | 是 |
| `test_extract_safe_split_table` | POST `/parse_pdf/extract_safe_split_table` | 提取安全分项表 | 是 |

### 5. `/warning` — 告警处置报告接口 (`test_warning_routes.py`)

| 测试方法 | 路由 | 说明 | 需文件 |
|---------|------|------|--------|
| `test_warning_analyze` | POST `/warning/analyze` | 告警报告研判 | 是(.docx) |
| `test_generate_notice_doc` | POST `/warning/generate_notice_doc` | 生成整改通知单 | 否 |
| `test_save_warning_report` | POST `/warning/save_warning_report` | 保存告警报告 | 是(.docx) |
| `test_delete_warning_report` | POST `/warning/delete_warning_report` | 删除告警报告 | 否 |

### 6. `/warning_handle` — 平台告警接口 (`test_platform_warning_routes.py`)

| 测试方法 | 路由 | 说明 |
|---------|------|------|
| `test_platform_warning` | POST `/warning_handle/warning` | 接收平台告警数据 |

### 7. `/ticket` — 工单接口 (`test_ticket_routes.py`)

| 测试方法 | 路由 | 说明 |
|---------|------|------|
| `test_associate_device` | POST `/ticket/associate_device` | 关联设备（变电站） |
| `test_associate_device_not_substation` | POST `/ticket/associate_device` | 关联设备（非变电站） |

---

## 常用参数

| 参数 | 说明 |
|------|------|
| `-s` | 禁用输出捕获，显示 print 内容 |
| `-v` | 详细输出模式 |
| `-x` | 遇到第一个失败即停止 |
| `--tb=short` | 简短的错误回溯 |
| `-k <关键字>` | 按名称模糊匹配，如 `-k chat` 运行所有名称含 chat 的测试 |
