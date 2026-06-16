"""
任务仓库 - 任务和任务-规则关联表的数据访问层
"""
from typing import List

from csm_ai_service.server.protection_audit.audit.audit_graph import RuleAuditResult
from csm_ai_service.server.db.models import AuditResultModel
from csm_ai_service.server.db.session import with_session


# ==================== AuditResult 审计结果表操作 ====================

@with_session
def add_audit_result(
        session,
        task_id: int,
        rule_id: int,
        contract_id: int,
        is_compliant: bool = False,
) -> int:
    """
    新增审计结果记录，返回自增ID
    """
    m = AuditResultModel(
        task_id=task_id,
        rule_id=rule_id,
        contract_id=contract_id,
        is_compliant=is_compliant,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def get_audit_results_by_task_id(session, task_id: int) -> List[RuleAuditResult]:
    """
    获取指定任务的所有审计结果
    """
    results = session.query(AuditResultModel).filter_by(task_id=task_id) \
        .order_by(AuditResultModel.id).all()
    return [_audit_result_to_dict(r) for r in results]


@with_session
def update_audit_result(
        session,
        result_id: int,
        is_compliant: bool = None,
        rule_name: str = None,
        rule_description: str = None,
        rule_judge_logic: str = None,
        conclusion: str = None,
        reasoning: str = None,
        origin_text: str = None,
        related_chapters: list = None,
        related_text: str = None,
        related_doc_ids: list = None,
) -> bool:
    """
    更新审计结果
    """
    m = session.query(AuditResultModel).filter_by(id=result_id).first()
    if m is None:
        return False
    if is_compliant is not None:
        m.is_compliant = is_compliant
    if rule_name is not None:
        m.rule_name = rule_name
    if rule_description is not None:
        m.rule_description = rule_description
    if rule_judge_logic is not None:
        m.rule_judge_logic = rule_judge_logic
    if conclusion is not None:
        m.conclusion = conclusion
    if reasoning is not None:
        m.reasoning = reasoning
    if origin_text is not None:
        m.origin_text = origin_text
    if related_chapters is not None:
        m.related_chapters = related_chapters
    if related_text is not None:
        m.related_text = related_text
    if related_doc_ids is not None:
        m.related_doc_ids = related_doc_ids
    session.add(m)
    session.commit()
    return True


@with_session
def delete_audit_results_by_task_id(session, task_id: int) -> int:
    """
    删除指定任务的所有审计结果
    """
    result = session.query(AuditResultModel).filter_by(task_id=task_id).delete()
    session.commit()
    return result


@with_session
def batch_add_audit_results(
        session,
        task_id: int,
        contract_id: int,
        rule_ids: List[int],
) -> List[int]:
    """
    批量创建审计结果（初始化时，结果状态均为 False）
    返回创建的ID列表
    """
    ids = []
    for rule_id in rule_ids:
        m = AuditResultModel(
            task_id=task_id,
            rule_id=rule_id,
            contract_id=contract_id,
            is_compliant=False,
        )
        session.add(m)
        session.flush()
        ids.append(m.id)
    session.commit()
    return ids


# ==================== 辅助函数 ====================


def _audit_result_to_dict(r: AuditResultModel) -> RuleAuditResult:
    """将AuditResultModel转换为RuleAuditResult对象"""
    return RuleAuditResult(
        contract_id=r.contract_id,
        rule_id=r.rule_id,
        rule_name=r.rule_name or "",
        rule_description=r.rule_description or "",
        rule_judge_logic=r.rule_judge_logic or "",
        related_chapters=r.related_chapters or [],
        related_text=r.related_text or "",
        related_doc_ids=r.related_doc_ids or [],
        is_compliant=r.is_compliant if r.is_compliant is not None else False,
        conclusion=r.conclusion or "",
        reasoning=r.reasoning or "",
        origin_text=r.origin_text or "",
    )
