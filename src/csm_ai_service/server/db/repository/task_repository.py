"""
任务仓库 - 任务和任务-规则关联表的数据访问层
"""
from typing import List, Optional
from sqlalchemy import desc
from csm_ai_service.server.db.models import TaskModel
from csm_ai_service.server.db.session import with_session


# ==================== Task 任务表操作 ====================

@with_session
def add_task(
    session,
    contract_id: int,
    status: str = "pending",
) -> int:
    """
    新增任务记录，返回自增ID

    Args:
        contract_id: 合同ID
        status: 任务状态
    """
    m = TaskModel(
        contract_id=contract_id,
        status=status,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def get_task_by_id(session, task_id: int) -> Optional[dict]:
    """
    根据ID获取任务，返回字典
    """
    t = session.query(TaskModel).filter_by(id=task_id).first()
    if t is None:
        return None
    return _task_to_dict(t)


@with_session
def get_task_by_contract_id(session, contract_id: int) -> Optional[dict]:
    """
    根据合同ID获取最近的任务
    """
    t = session.query(TaskModel).filter_by(contract_id=contract_id) \
        .order_by(desc(TaskModel.create_time)).first()
    if t is None:
        return None
    return _task_to_dict(t)


@with_session
def list_tasks(
    session,
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """
    获取任务列表，按时间倒序
    """
    tasks = session.query(TaskModel) \
        .order_by(desc(TaskModel.create_time)) \
        .offset(offset).limit(limit).all()
    return [_task_to_dict(t) for t in tasks]


@with_session
def update_task(
    session,
    task_id: int,
    status: str = None,
    ocr_status: str = None,
    audit_status: str = None,
    audit_report: str = None,
    error_message: str = None,
    ocr_start_time=None,
    ocr_end_time=None,
    audit_start_time=None,
    audit_end_time=None,
) -> bool:
    """
    更新任务信息（只更新传入的非None字段）
    """
    m = session.query(TaskModel).filter_by(id=task_id).first()
    if m is None:
        return False
    if status is not None:
        m.status = status
    if ocr_status is not None:
        m.ocr_status = ocr_status
    if audit_status is not None:
        m.audit_status = audit_status
    if audit_report is not None:
        m.audit_report = audit_report
    if error_message is not None:
        m.error_message = error_message
    if ocr_start_time is not None:
        m.ocr_start_time = ocr_start_time
    if ocr_end_time is not None:
        m.ocr_end_time = ocr_end_time
    if audit_start_time is not None:
        m.audit_start_time = audit_start_time
    if audit_end_time is not None:
        m.audit_end_time = audit_end_time
    session.add(m)
    session.commit()
    return True


@with_session
def delete_task(session, task_id: int) -> bool:
    """
    删除任务记录
    """
    result = session.query(TaskModel).filter_by(id=task_id).delete()
    session.commit()
    return result > 0




# ==================== 辅助函数 ====================

def _task_to_dict(t: TaskModel) -> dict:
    """将TaskModel转换为字典（路径通过 contract_id 动态查找）"""
    return {
        "id": t.id,
        "contract_id": t.contract_id,
        "status": t.status,
        "ocr_status": t.ocr_status,
        "audit_status": t.audit_status,
        "audit_report": t.audit_report,
        "error_message": t.error_message,
        "create_time": t.create_time.strftime("%Y-%m-%d %H:%M:%S") if t.create_time else None,
        "update_time": t.update_time.strftime("%Y-%m-%d %H:%M:%S") if t.update_time else None,
        "ocr_start_time": t.ocr_start_time.strftime("%Y-%m-%d %H:%M:%S") if t.ocr_start_time else None,
        "ocr_end_time": t.ocr_end_time.strftime("%Y-%m-%d %H:%M:%S") if t.ocr_end_time else None,
        "audit_start_time": t.audit_start_time.strftime("%Y-%m-%d %H:%M:%S") if t.audit_start_time else None,
        "audit_end_time": t.audit_end_time.strftime("%Y-%m-%d %H:%M:%S") if t.audit_end_time else None,
    }