"""
历史告警处置报告 & 告警处置规则库 数据访问层
"""
import io
import json
from typing import Dict, List, Optional

from sqlalchemy import desc, or_

from csm_ai_service.server.db.models.alert_model import AlertReportModel, AlertRuleModel
from csm_ai_service.server.db.session import with_session
from csm_ai_service.server.db.repository.search_index import build_index_text, tokenize, calc_relevance_score


# ==================== 告警报告 CRUD ====================

@with_session
def add_alert_report(
    session,
    report_title: str,
    file_name: str = "",
    alert_content: str = "",
    meta_info: Dict = None,
    full_text: str = "",
    table_data_text: str = "",
    status: str = "cache",
) -> int:
    """新增告警处置报告，对告警内容自动构建全文索引，返回自增ID。默认status=cache（缓存状态）。
    file_name作为唯一键，若已存在则返回已有ID。"""
    if file_name:
        existing = session.query(AlertReportModel).filter_by(file_name=file_name).first()
        if existing:
           return existing.id
    keywords_index = build_index_text(alert_content)
    meta_info_str = json.dumps(meta_info, ensure_ascii=False) if meta_info else ""
    m = AlertReportModel(
        report_title=report_title,
        file_name=file_name,
        alert_content=alert_content,
        meta_info=meta_info_str,
        full_text=full_text,
        table_data_text=table_data_text,
        keywords_index=keywords_index,
        status=status,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def get_alert_report_by_id(session, report_id: int) -> Optional[dict]:
    """根据ID获取告警报告"""
    r = session.query(AlertReportModel).filter_by(id=report_id).first()
    if r is None:
        return None
    return _report_to_dict(r)


@with_session
def get_alert_report_by_file_name(session, file_name: str) -> Optional[dict]:
    """根据file_name获取告警报告"""
    r = session.query(AlertReportModel).filter_by(file_name=file_name).first()
    if r is None:
        return None
    return _report_to_dict(r)


@with_session
def list_alert_reports(
    session,
    limit: int = 50,
    offset: int = 0,
    status: str = None,
) -> List[dict]:
    """获取告警报告列表，按时间倒序。可按status筛选：cache/saved，None则返回全部"""
    q = session.query(AlertReportModel)
    if status is not None:
        q = q.filter_by(status=status)
    reports = q.order_by(desc(AlertReportModel.update_time)).offset(offset).limit(limit).all()
    return [_report_to_dict(r) for r in reports]


@with_session
def update_alert_report(
    session,
    report_id: int,
    report_title: str = None,
    file_name: str = None,
    alert_content: str = None,
    meta_info: Dict = None,
    full_text: str = None,
    table_data_text: str = None,
    status: str = None,
) -> bool:
    """更新告警报告，告警内容变更时自动重建全文索引"""
    m = session.query(AlertReportModel).filter_by(id=report_id).first()
    if m is None:
        return False
    if report_title is not None:
        m.report_title = report_title
    if file_name is not None:
        m.file_name = file_name
    if alert_content is not None:
        m.alert_content = alert_content
    if meta_info is not None:
        m.meta_info = json.dumps(meta_info, ensure_ascii=False)
    if full_text is not None:
        m.full_text = full_text
    if table_data_text is not None:
        m.table_data_text = table_data_text
    if status is not None:
        m.status = status
    # 重建索引（对告警内容建索引）
    m.keywords_index = build_index_text(m.alert_content or "")
    session.add(m)
    session.commit()
    return True


@with_session
def confirm_alert_report(session, report_id: int) -> bool:
    """将告警报告从缓存状态确认保存为正式状态（status: cache -> saved）"""
    m = session.query(AlertReportModel).filter_by(id=report_id).first()
    if m is None:
        return False
    m.status = "saved"
    session.add(m)
    session.commit()
    return True


@with_session
def delete_alert_report(session, report_id: int) -> bool:
    """删除告警报告"""
    result = session.query(AlertReportModel).filter_by(id=report_id).delete()
    session.commit()
    return result > 0


@with_session
def search_alert_reports(
    session,
    query: str,
    top_k: int = 20,
    status: str = "saved",
) -> List[dict]:
    """
    全文检索告警报告：使用 jieba 分词后，对 keywords_index 做 LIKE 匹配，
    并计算相关度得分排序返回。默认只查询已保存的报告（status=saved），传None则查询全部。
    """
    if not query:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # 构建 SQL LIKE 条件：每个分词只要命中索引即匹配
    filters = []
    for token in query_tokens:
        filters.append(AlertReportModel.keywords_index.like(f"%{token}%"))
    q = session.query(AlertReportModel).filter(or_(*filters))
    if status is not None:
        q = q.filter_by(status=status)
    results = q.order_by(desc(AlertReportModel.update_time)).limit(top_k * 3).all()

    # 计算相关度并排序
    scored = []
    for r in results:
        score = calc_relevance_score(r.keywords_index or "", query)
        scored.append((_report_to_dict(r), score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, score in scored[:top_k]]


# ==================== 告警规则 CRUD ====================

@with_session
def add_alert_rule(
    session,
    name: str,
    rule_code: str = "",
    description: str = "",
) -> int:
    """新增告警处置规则，对规则名称+描述自动构建全文索引，返回自增ID。
    rule_code作为唯一键，若已存在则返回已有ID。"""
    if rule_code:
        existing = session.query(AlertRuleModel).filter_by(rule_code=rule_code).first()
        if existing:
            return existing.id
    keywords_index = build_index_text(name, description)
    m = AlertRuleModel(
        rule_code=rule_code,
        name=name,
        description=description,
        keywords_index=keywords_index,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def get_alert_rule_by_id(session, rule_id: int) -> Optional[dict]:
    """根据ID获取告警规则"""
    r = session.query(AlertRuleModel).filter_by(id=rule_id).first()
    if r is None:
        return None
    return _rule_to_dict(r)


@with_session
def list_alert_rules(
    session,
    limit: int = 50,
    offset: int = 0,
) -> List[dict]:
    """获取告警规则列表，按时间倒序"""
    q = session.query(AlertRuleModel)
    rules = q.order_by(desc(AlertRuleModel.update_time)).offset(offset).limit(limit).all()
    return [_rule_to_dict(r) for r in rules]


@with_session
def update_alert_rule(
    session,
    rule_id: int,
    name: str = None,
    rule_code: str = None,
    description: str = None,
) -> bool:
    """更新告警规则，变更时自动重建全文索引"""
    m = session.query(AlertRuleModel).filter_by(id=rule_id).first()
    if m is None:
        return False
    if name is not None:
        m.name = name
    if rule_code is not None:
        m.rule_code = rule_code
    if description is not None:
        m.description = description
    # 重建索引
    m.keywords_index = build_index_text(m.name or "", m.description or "")
    session.add(m)
    session.commit()
    return True


@with_session
def delete_alert_rule(session, rule_id: int) -> bool:
    """删除告警规则"""
    result = session.query(AlertRuleModel).filter_by(id=rule_id).delete()
    session.commit()
    return result > 0


@with_session
def search_alert_rules(
    session,
    query: str,
    top_k: int = 20,
) -> List[dict]:
    """
    全文检索告警规则：使用 jieba 分词后，对 keywords_index 做 LIKE 匹配，
    并计算相关度得分排序返回。
    """
    if not query:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    filters = []
    for token in query_tokens:
        filters.append(AlertRuleModel.keywords_index.like(f"%{token}%"))
    results = session.query(AlertRuleModel).filter(or_(*filters)) \
        .order_by(desc(AlertRuleModel.update_time)).limit(top_k * 3).all()

    scored = []
    for r in results:
        score = calc_relevance_score(r.keywords_index or "", query)
        scored.append((_rule_to_dict(r), score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, score in scored[:top_k]]


# ==================== 辅助函数 ====================

def _report_to_dict(r: AlertReportModel) -> dict:
    meta_info = {}
    if r.meta_info:
        try:
            meta_info = json.loads(r.meta_info)
        except (json.JSONDecodeError, TypeError):
            meta_info = {}
    return {
        "id": r.id,
        "report_title": r.report_title or "",
        "alert_content": r.alert_content or "",
        "meta_info": meta_info,
        "file_name": r.file_name or "",
        "full_text": r.full_text or "",
        "table_data_text": r.table_data_text or "",
        "status": r.status or "cache",
        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
        "update_time": r.update_time.strftime("%Y-%m-%d %H:%M:%S") if r.update_time else None,
    }


def _rule_to_dict(r: AlertRuleModel) -> dict:
    return {
        "id": r.id,
        "rule_code": r.rule_code or "",
        "name": r.name or "",
        "description": r.description or "",
        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
        "update_time": r.update_time.strftime("%Y-%m-%d %H:%M:%S") if r.update_time else None,
    }


# ==================== 告警报告 导入导出 ====================

# Excel列头与字段的映射
_EXPORT_COLUMNS = [
    ("报告标题", "report_title"),
    ("文件名称", "file_name"),
    ("告警内容", "alert_content"),
    ("告警元信息", "meta_info"),
    ("文档段落文本", "full_text"),
    ("文档表格数据", "table_data_text"),
    ("状态", "status"),
    ("创建时间", "create_time"),
    ("更新时间", "update_time"),
]


@with_session
def export_alert_reports_to_excel(session) -> bytes:
    """导出所有告警处置报告到Excel，返回Excel文件的二进制内容"""
    from openpyxl import Workbook

    reports = session.query(AlertReportModel).order_by(desc(AlertReportModel.update_time)).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "告警处置报告"

    # 写入表头
    headers = [col[0] for col in _EXPORT_COLUMNS]
    ws.append(headers)

    # 写入数据
    for r in reports:
        row = []
        for _, field in _EXPORT_COLUMNS:
            if field == "meta_info":
                val = r.meta_info or ""
            else:
                val = getattr(r, field, "")
                if val is None:
                    val = ""
                # 时间字段格式化
                if field in ("create_time", "update_time") and hasattr(val, "strftime"):
                    val = val.strftime("%Y-%m-%d %H:%M:%S")
            row.append(val)
        ws.append(row)

    # 调整列宽
    col_widths = [30, 25, 50, 40, 50, 50, 10, 20, 20]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@with_session
def import_alert_reports_from_excel(session, file_bytes: bytes) -> dict:
    """从Excel文件导入告警处置报告，按file_name去重（已存在则跳过），返回导入结果统计"""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(min_row=1, values_only=True))
    if not rows:
        return {"inserted": 0, "skipped": 0, "errors": []}

    # 读取表头，建立列索引
    header_row = rows[0]
    header_map = {}
    for col_idx, col_val in enumerate(header_row):
        if col_val:
            for cn, fn in _EXPORT_COLUMNS:
                if cn == str(col_val).strip():
                    header_map[fn] = col_idx
                    break

    inserted = 0
    skipped = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            def get_val(field):
                idx = header_map.get(field)
                if idx is None or idx >= len(row):
                    return ""
                val = row[idx]
                return str(val) if val is not None else ""

            report_title = get_val("report_title")
            file_name = get_val("file_name")
            alert_content = get_val("alert_content")
            meta_info_str = get_val("meta_info")
            full_text = get_val("full_text")
            table_data_text = get_val("table_data_text")
            status = get_val("status") or "cache"

            if not report_title:
                errors.append(f"第{row_idx}行：报告标题为空，跳过")
                continue

            # 按file_name去重
            if file_name:
                existing = session.query(AlertReportModel).filter_by(file_name=file_name).first()
                if existing:
                    skipped += 1
                    continue

            # 解析meta_info
            meta_info = {}
            if meta_info_str:
                try:
                    meta_info = json.loads(meta_info_str)
                except (json.JSONDecodeError, TypeError):
                    meta_info = {}

            keywords_index = build_index_text(alert_content)
            meta_info_str_clean = json.dumps(meta_info, ensure_ascii=False) if meta_info else ""

            m = AlertReportModel(
                report_title=report_title,
                file_name=file_name,
                alert_content=alert_content,
                meta_info=meta_info_str_clean,
                full_text=full_text,
                table_data_text=table_data_text,
                keywords_index=keywords_index,
                status=status,
            )
            session.add(m)
            session.commit()
            inserted += 1
        except Exception as e:
            errors.append(f"第{row_idx}行：{str(e)}")
            continue

    wb.close()
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


# ==================== 告警规则 导入导出 ====================

_RULE_EXPORT_COLUMNS = [
    ("规则编号", "rule_code"),
    ("规则名称", "name"),
    ("规则详细描述", "description"),
    ("创建时间", "create_time"),
    ("更新时间", "update_time"),
]


@with_session
def export_alert_rules_to_excel(session) -> bytes:
    """导出所有告警处置规则到Excel，返回Excel文件的二进制内容"""
    from openpyxl import Workbook

    rules = session.query(AlertRuleModel).order_by(desc(AlertRuleModel.update_time)).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "告警处置规则"

    headers = [col[0] for col in _RULE_EXPORT_COLUMNS]
    ws.append(headers)

    for r in rules:
        row = []
        for _, field in _RULE_EXPORT_COLUMNS:
            val = getattr(r, field, "")
            if val is None:
                val = ""
            if field in ("create_time", "update_time") and hasattr(val, "strftime"):
                val = val.strftime("%Y-%m-%d %H:%M:%S")
            row.append(val)
        ws.append(row)

    col_widths = [15, 25, 60, 20, 20]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@with_session
def import_alert_rules_from_excel(session, file_bytes: bytes) -> dict:
    """从Excel文件导入告警处置规则，按rule_code去重（已存在则跳过），返回导入结果统计"""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(min_row=1, values_only=True))
    if not rows:
        return {"inserted": 0, "skipped": 0, "errors": []}

    header_row = rows[0]
    header_map = {}
    for col_idx, col_val in enumerate(header_row):
        if col_val:
            for cn, fn in _RULE_EXPORT_COLUMNS:
                if cn == str(col_val).strip():
                    header_map[fn] = col_idx
                    break

    inserted = 0
    skipped = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            def get_val(field):
                idx = header_map.get(field)
                if idx is None or idx >= len(row):
                    return ""
                val = row[idx]
                return str(val) if val is not None else ""

            rule_code = get_val("rule_code")
            name = get_val("name")
            description = get_val("description")

            if not name:
                errors.append(f"第{row_idx}行：规则名称为空，跳过")
                continue

            # 按rule_code去重
            if rule_code:
                existing = session.query(AlertRuleModel).filter_by(rule_code=rule_code).first()
                if existing:
                    skipped += 1
                    continue

            keywords_index = build_index_text(name, description)

            m = AlertRuleModel(
                rule_code=rule_code,
                name=name,
                description=description,
                keywords_index=keywords_index,
            )
            session.add(m)
            session.commit()
            inserted += 1
        except Exception as e:
            errors.append(f"第{row_idx}行：{str(e)}")
            continue

    wb.close()
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


# ==================== 默认规则定义 ====================

DEFAULT_ALERT_RULES = [
    {
        "rule_code": "RULE_001",
        "name": "内容完整性检查",
        "description": "内容要完整，包括原因分析、整改结果、佐证材料等内容，关键信息无缺失。如设备的型号、故障排查过程，是否举一反三进行了全面排查和整改等。",
    },
    {
        "rule_code": "RULE_002",
        "name": "逻辑一致性检查",
        "description": "由大模型对报告全文进行阅读，分析有没有逻辑不通的内容，比如前后不一致、原因分析与处置措施没有关联关系等等，结合知识库判断内容有没有错误的地方。",
    },
    {
        "rule_code": "RULE_003",
        "name": "四不放过原则检查",
        "description": "针对有威胁的告警，目前就是违规外联这一种类型的告警，要按照四不放过原则去审视告警分析报告，事故原因有没有查清楚、有没有对责任人员的处理结果、报告中的整改措施有没有落实的佐证、有关人员有没有受到教育比如有没有培训记录等等。读分析报告有没有做到这四个方面。",
    },
]


@with_session
def init_default_alert_rules(session) -> List[int]:
    """初始化默认告警处置规则：若规则名称不存在则插入，已存在则跳过，返回本次插入的规则ID列表"""
    inserted_ids = []
    for rule in DEFAULT_ALERT_RULES:
        existing = session.query(AlertRuleModel).filter_by(rule_code=rule["rule_code"]).first()
        if not existing:
            keywords_index = build_index_text(rule["name"], rule["description"])
            m = AlertRuleModel(
                rule_code=rule["rule_code"],
                name=rule["name"],
                description=rule["description"],
                keywords_index=keywords_index,
            )
            session.add(m)
            session.commit()
            inserted_ids.append(m.id)
    return inserted_ids
