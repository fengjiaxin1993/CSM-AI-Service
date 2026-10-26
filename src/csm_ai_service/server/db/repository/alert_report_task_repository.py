"""
预警报告审计任务仓库 - AlertReportTaskModel 的数据访问层
"""
import json
from typing import List, Optional
from sqlalchemy import desc
from csm_ai_service.server.db.models.alert_report_task_model import AlertReportTaskModel
from csm_ai_service.server.db.session import with_session


# ==================== CRUD ====================

@with_session
def add_alert_report_task(
    session,
    task_id: str,
    file_id: str,
    file_name: str,
    content_hash: str,
    status: str = "pending",
    file_path: str = "",
) -> str:
    """
    新增预警报告审计任务记录，返回 task_id
    """
    m = AlertReportTaskModel(
        task_id=task_id,
        file_id=file_id,
        file_name=file_name,
        file_path=file_path,
        content_hash=content_hash,
        status=status,
    )
    session.add(m)
    session.commit()
    return m.task_id


@with_session
def get_alert_report_task_by_id(session, task_id: str) -> Optional[dict]:
    """根据 task_id 获取任务，返回字典"""
    t = session.query(AlertReportTaskModel).filter_by(task_id=task_id).first()
    if t is None:
        return None
    return _task_to_dict(t)



@with_session
def list_alert_report_tasks(
    session,
    limit: int = 100,
    offset: int = 0,
    status: str = None,
) -> List[dict]:
    """获取任务列表，按时间倒序，可按 status 筛选"""
    q = session.query(AlertReportTaskModel)
    if status:
        q = q.filter_by(status=status)
    tasks = q.order_by(desc(AlertReportTaskModel.create_time)) \
        .offset(offset).limit(limit).all()
    return [_task_to_dict(t) for t in tasks]


@with_session
def update_alert_report_task(
    session,
    task_id: str,
    status: str = None,
    pdf_status: str = None,
    audit_status: str = None,
    result_json: str = None,
    error_message: str = None,
    file_path: str = None,
    pdf_start_time=None,
    pdf_end_time=None,
    audit_start_time=None,
    audit_end_time=None,
) -> bool:
    """更新任务信息（只更新传入的非None字段）"""
    m = session.query(AlertReportTaskModel).filter_by(task_id=task_id).first()
    if m is None:
        return False
    if file_path is not None:
        m.file_path = file_path
    if status is not None:
        m.status = status
    if pdf_status is not None:
        m.pdf_status = pdf_status
    if audit_status is not None:
        m.audit_status = audit_status
    if result_json is not None:
        m.result_json = result_json
    if error_message is not None:
        m.error_message = error_message
    if pdf_start_time is not None:
        m.pdf_start_time = pdf_start_time
    if pdf_end_time is not None:
        m.pdf_end_time = pdf_end_time
    if audit_start_time is not None:
        m.audit_start_time = audit_start_time
    if audit_end_time is not None:
        m.audit_end_time = audit_end_time
    session.add(m)
    session.commit()
    return True


@with_session
def delete_alert_report_task(session, task_id: str) -> bool:
    """删除任务记录"""
    result = session.query(AlertReportTaskModel).filter_by(task_id=task_id).delete()
    session.commit()
    return result > 0


# ==================== 辅助函数 ====================

def _task_to_dict(t: AlertReportTaskModel) -> dict:
    """将 AlertReportTaskModel 转换为字典"""
    result_json = t.result_json
    # 尝试将 result_json 解析为 dict，方便前端使用
    if result_json and isinstance(result_json, str):
        try:
            result_json = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "task_id": t.task_id,
        "file_id": t.file_id,
        "file_name": t.file_name,
        "file_path": t.file_path or "",
        "content_hash": t.content_hash,
        "status": t.status,
        "pdf_status": t.pdf_status,
        "audit_status": t.audit_status,
        "result_json": result_json,
        "error_message": t.error_message,
        "create_time": t.create_time.strftime("%Y-%m-%d %H:%M:%S") if t.create_time else None,
        "update_time": t.update_time.strftime("%Y-%m-%d %H:%M:%S") if t.update_time else None,
        "pdf_start_time": t.pdf_start_time.strftime("%Y-%m-%d %H:%M:%S") if t.pdf_start_time else None,
        "pdf_end_time": t.pdf_end_time.strftime("%Y-%m-%d %H:%M:%S") if t.pdf_end_time else None,
        "audit_start_time": t.audit_start_time.strftime("%Y-%m-%d %H:%M:%S") if t.audit_start_time else None,
        "audit_end_time": t.audit_end_time.strftime("%Y-%m-%d %H:%M:%S") if t.audit_end_time else None,
    }
