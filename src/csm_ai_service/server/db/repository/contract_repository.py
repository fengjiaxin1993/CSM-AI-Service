import os
from typing import List, Optional
from sqlalchemy import desc
from csm_ai_service.server.db.models import ContractModel
from csm_ai_service.server.db.session import with_session
from csm_ai_service.settings import Settings


@with_session
def get_contract_by_name(session, file_name: str) -> Optional[dict]:
    """
    根据文件名查找合同，返回字典；不存在返回None
    """
    c = session.query(ContractModel).filter_by(file_name=file_name).first()
    if c is None:
        return None
    return _contract_to_dict(c)


@with_session
def add_contract(
    session,
    file_name: str,
    file_size: int = 0,
    file_type: str = "pdf",
    status: str = "pending",
) -> int:
    """
    新增合同记录，返回自增ID。
    如果已存在同名文件，直接返回已有记录的ID，不重复创建。
    """
    existing = session.query(ContractModel).filter_by(file_name=file_name).first()
    if existing:
        return existing.id

    m = ContractModel(
        file_name=file_name,
        file_size=file_size,
        file_type=file_type,
        status=status,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def get_contract_by_id(session, contract_id: int) -> Optional[dict]:
    """
    根据ID获取合同，返回字典
    """
    c = session.query(ContractModel).filter_by(id=contract_id).first()
    if c is None:
        return None
    return _contract_to_dict(c)


@with_session
def list_contracts(
    session,
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """
    获取合同列表，按时间倒序
    """
    contracts = session.query(ContractModel) \
        .order_by(desc(ContractModel.update_time)) \
        .offset(offset).limit(limit).all()
    return [_contract_to_dict(c) for c in contracts]


@with_session
def update_contract(
    session,
    contract_id: int,
    file_name: str = None,
    file_size: int = None,
    file_type: str = None,
    status: str = None,
) -> bool:
    """
    更新合同信息（只更新传入的非None字段）
    """
    m = session.query(ContractModel).filter_by(id=contract_id).first()
    if m is None:
        return False
    if file_name is not None:
        m.file_name = file_name
    if file_size is not None:
        m.file_size = file_size
    if file_type is not None:
        m.file_type = file_type
    if status is not None:
        m.status = status
    session.add(m)
    session.commit()
    return True


@with_session
def delete_contract(session, contract_id: int) -> bool:
    """
    删除合同记录
    """
    result = session.query(ContractModel).filter_by(id=contract_id).delete()
    session.commit()
    return result > 0


@with_session
def contract_exists(session, contract_id: int) -> bool:
    """
    检查合同是否存在
    """
    return session.query(ContractModel).filter_by(id=contract_id).first() is not None


def _contract_to_dict(c: ContractModel) -> dict:
    """将 ContractModel 转换为字典（数据库不存路径，动态拼接）"""
    file_path = os.path.join(Settings.basic_settings.UPLOADS_DIR, c.file_name) if c.file_name else ""
    return {
        "id": c.id,
        "file_name": c.file_name,
        "file_path": file_path,
        "file_size": c.file_size,
        "file_type": c.file_type,
        "status": c.status,
        "create_time": c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else None,
        "update_time": c.update_time.strftime("%Y-%m-%d %H:%M:%S") if c.update_time else None,
    }
