# 接口测试说明

## 前置条件

1. **启动服务**：确保 CSM-AI-Service 已在 `http://127.0.0.1:7861` 运行
2. **安装依赖**：
   ```bash
   pip install pytest pytest-asyncio pytest-order httpx
   ```
3. **测试文件**：部分测试依赖真实文件，需放在 `pytest/data/` 目录下：

   | 文件名 | 依赖的测试 |
   |--------|-----------|
   | `《电力监控系统安全防护规定》27号令.pdf` | `test_chat_routes::test_unified_chat_with_file` |
   | `2018泉州供电公司调度自动化系统信息安全等级测评报告-S2A3G3.pdf` | `test_pdf_extract_routes`（全部） |
   | `关于110kVXX变告警说明.docx` | `test_warning_routes`（告警分析、保存报告） |
   | `页面提取自－草台第一分散式电站电力监控系统二次安全防护实施方案.pdf` | `test_ocr_contract_task_routes`（上传合同） |

---

## 测试文件一览

| 文件 | 对应接口 | 是否有顺序依赖 | 说明 |
|------|---------|---------------|------|
| `test_chat_routes.py` | `/chat` | 否 | 对话类接口，可单独运行 |
| `test_chat_manager_routes.py` | `/chat_manager` | 否 | 对话管理，可单独运行 |
| `test_kb_routes.py` | `/knowledge_base` | 否 | 知识库管理，可单独运行 |
| `test_pdf_extract_routes.py` | `/parse_pdf` | 否 | PDF安全表提取，需PDF文件 |
| `test_warning_routes.py` | `/warning` | **是（order 1→2→3）** | 告警处置报告，有严格顺序 |
| `test_platform_warning_routes.py` | `/warning_handle` | 否 | 平台告警，可单独运行 |
| `test_ticket_routes.py` | `/ticket` | 否 | 工单接口，可单独运行 |
| `test_audit_rule_routes.py` | `/api/rules` | **是（order 1→7）** | 审计规则CRUD，有严格顺序 |
| `test_ocr_contract_task_routes.py` | OCR/合同/任务/审计结果 | **是（order 1→9）** | 全流程测试，有严格顺序 |

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

# 告警处置报告接口（有顺序，需安装 pytest-order）
pytest test_warning_routes.py -s -v

# 平台告警接口
pytest test_platform_warning_routes.py -s -v

# 工单接口
pytest test_ticket_routes.py -s -v

# 审计规则接口（有顺序，需安装 pytest-order）
pytest test_audit_rule_routes.py -s -v

# OCR/合同/任务/审计结果 全流程（有顺序，需安装 pytest-order）
pytest test_ocr_contract_task_routes.py -s -v
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

# 例：只测试OCR全流程中的上传步骤
pytest test_ocr_contract_task_routes.py::test_upload_contract_with_pdf -s -v
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
| `test_agent_chat1/2/3` | POST `/chat/chat_agent` | Agent 对话（多轮） |
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

> **有严格执行顺序**：`test_warning_analyze` → `test_save_warning_report` → `test_delete_warning_report`

| 顺序 | 测试方法 | 路由 | 说明 | 需文件 |
|------|---------|------|------|--------|
| 1 | `test_warning_analyze` | POST `/warning/analyze` | 告警报告研判 | 是(.docx) |
| 2 | `test_save_warning_report` | POST `/warning/save_warning_report` | 保存告警报告 | 是(.docx) |
| 3 | `test_delete_warning_report` | POST `/warning/delete_warning_report` | 删除告警报告 | 否 |
| - | `test_generate_notice_doc` | POST `/warning/generate_notice_doc` | 生成整改通知单 | 否 |

### 6. `/warning_handle` — 平台告警接口 (`test_platform_warning_routes.py`)

| 测试方法 | 路由 | 说明 |
|---------|------|------|
| `test_platform_warning` | POST `/warning_handle/warning` | 接收平台告警数据 |

### 7. `/ticket` — 工单接口 (`test_ticket_routes.py`)

| 测试方法 | 路由 | 说明 |
|---------|------|------|
| `test_associate_device` | POST `/ticket/associate_device` | 关联设备（变电站） |
| `test_associate_device_not_substation` | POST `/ticket/associate_device` | 关联设备（非变电站） |

### 8. `/api/rules` — 审计规则管理接口 (`test_audit_rule_routes.py`)

> **有严格执行顺序**：初始化 → 列表 → 创建 → 详情 → 更新 → 删除

| 顺序 | 测试方法 | 路由 | 说明 |
|------|---------|------|------|
| 1 | `test_init_default_rules` | POST `/api/rules/init_default` | 导入默认规则 |
| 2 | `test_list_rules` | GET `/api/rules/list` | 获取规则列表 |
| 3 | `test_create_rule` | POST `/api/rules/create` | 创建新规则 |
| 4 | `test_get_rule_detail` | GET `/api/rules/detail/{id}` | 查询规则详情 |
| 5 | `test_update_rule` | POST `/api/rules/update/{id}` | 更新规则 |
| 6 | `test_delete_rule` | POST `/api/rules/delete/{id}` | 删除规则 |
| 7 | `test_get_rule_detail_not_found` | GET `/api/rules/detail/99999` | 查询不存在的规则 |

### 9. OCR/合同/任务/审计结果 — 全流程接口 (`test_ocr_contract_task_routes.py`)

> **有严格执行顺序**，全局变量传递 `_contract_id`、`_task_id`、`_file_path`，前置步骤失败则后续自动跳过

| 顺序 | 测试方法 | 路由 | 说明 |
|------|---------|------|------|
| 1 | `test_upload_contract_with_pdf` | POST `/api/upload` | 上传合同PDF，保存 contract_id/task_id |
| 2 | `test_pdf_pages` | POST `/api/pdf_pages` | 获取PDF页面信息 |
| 3 | `test_task_status_polling` | GET `/api/task/status/{task_id}` | 轮询任务状态直到完成（每10s查一次，最长10min） |
| 4 | `test_get_audit_result` | POST `/api/get_audit_result` | 获取审计结果（合同字段提取） |
| 5 | `test_get_audit_results_by_task` | GET `/api/audit-results/task/{task_id}` | 根据task_id查询审计结果 |
| 5 | `test_get_audit_results_not_found` | GET `/api/audit-results/task/99999` | 查询不存在的审计结果 |
| 6 | `test_list_contracts` | GET `/api/contracts/list` | 获取合同列表 |
| 6 | `test_list_contracts_with_pagination` | GET `/api/contracts/list?limit=5&offset=0` | 带分页查询合同 |
| 6 | `test_get_contract_detail` | GET `/api/contracts/detail/{id}` | 查询刚上传的合同详情 |
| 6 | `test_get_contract_detail_not_found` | GET `/api/contracts/detail/99999` | 查询不存在的合同 |
| 6 | `test_delete_contract_not_found` | POST `/api/contracts/delete/99999` | 删除不存在的合同 |
| 7 | `test_list_tasks` | GET `/api/tasks` | 查看任务列表 |
| 7 | `test_list_tasks_with_pagination` | GET `/api/tasks?limit=5&offset=0` | 带分页查询任务 |
| 7 | `test_get_task` | GET `/api/tasks/{id}` | 查询刚创建的任务 |
| 7 | `test_get_task_by_contract` | GET `/api/tasks/contract/{id}` | 查询合同对应的任务 |
| 7 | `test_get_task_not_found` | GET `/api/tasks/99999` | 查询不存在的任务 |
| 7 | `test_reprocess_contract_not_found` | POST `/api/tasks/reprocess/99999` | 重新处理不存在的合同 |
| 8 | `test_delete_task` | POST `/api/tasks/delete/{id}` | 删除刚创建的任务（清理） |
| 9 | `test_delete_contract` | POST `/api/contracts/delete/{id}` | 删除刚上传的合同（清理） |

---

## 常用参数

| 参数 | 说明 |
|------|------|
| `-s` | 禁用输出捕获，显示 print 内容 |
| `-v` | 详细输出模式 |
| `-x` | 遇到第一个失败即停止 |
| `--tb=short` | 简短的错误回溯 |
| `-k <关键字>` | 按名称模糊匹配，如 `-k chat` 运行所有名称含 chat 的测试 |

---

## 注意事项

- **有顺序依赖的测试文件**需要安装 `pytest-order` 插件，否则 `@pytest.mark.order` 不生效，测试将按默认顺序执行可能导致失败
- `test_ocr_contract_task_routes.py` 的轮询步骤默认每 10 秒查询一次，最长等待 10 分钟，如 OCR/审计耗时较长可适当调整
- 告警接口 `test_warning_routes.py` 的三个方法有严格的先后关系：先分析 → 再保存 → 再删除
