from typing import List, Optional
from sqlalchemy import desc
from csm_ai_service.server.db.models import AuditRuleModel
from csm_ai_service.server.db.session import with_session

# 默认初始化规则列表
DEFAULT_AUDIT_RULES = [
    {
        "name": "法律法规及标准引用合规性判断",
        "description": "核查安全防护方案编制过程中引用的法律法规、企业标准是否规范，排查存在引用不相关法规、2024年12月之后编制的方案仍沿用14号令等不合规问题",
        "chapter_keywords": ["总则"],
        "judge_logic": "首先核查方案编制时间，若方案编制时间为2024年12月及以后，检查方案引用的规章制度是否仍包含14号令，存在即为不合规；其次逐一核对方案中所有引用的法律法规、企业标准，判断引用内容是否与电力监控系统安全防护、等保测评相关，存在无关法规、标准引用情况即为不合规"
    },
    {
        "name": "厂站基本情况描述完整性判断",
        "description": "核查安全防护方案中对厂站基本情况的描述内容是否完整，是否存在信息缺失问题",
        "chapter_keywords": ["系统概况"],
        "judge_logic": "对照电力监控系统安全防护方案编制规范要求，全面核查方案系统概况章节中厂站相关基础信息，包含电力监控系统架构、设备部署、业务运行、网络环境等核心信息，若存在任意一项关键信息缺失、描述模糊或未提及的情况，判定为描述不全、不合规"
    },
    {
        "name": "安全分区合理性判断",
        "description": "核查安全防护方案中规划的系统安全分区划分方式、分区边界设置等内容是否合理合规",
        "chapter_keywords": ["安全分区"],
        "judge_logic": "依据电力行业安全分区相关规范及等级保护要求，判断电力监控系统各业务系统、网络设备、终端设备的分区划分是否符合行业标准，分区边界界定是否清晰、分区划分逻辑是否合理，是否存在跨区混用、分区错位、分区划分不符合业务安全需求等不合理情况，存在问题即为不合规"
    },
    {
        "name": "设备清单信息完整性判断",
        "description": "核查方案附件中主要设备清单的信息是否完整，是否存在关键设备信息缺失问题",
        "chapter_keywords": ["主要设备清单"],
        "judge_logic": "核查附件1主要设备清单内容，逐一核对清单内设备名称、型号规格、设备数量、部署位置、设备用途、安全配置、接入网络区域等核心参数信息，若存在设备信息遗漏、关键参数空缺、设备统计不全、未涵盖电力监控系统核心防护及运行设备等情况，判定为设备清单信息不全、不合规"
    },
    {
        "name": "等级保护定级合理性判断",
        "description": "核查方案中电力监控系统等级保护定级结果是否合理、合规，定级依据是否充分",
        "chapter_keywords": ["安全防护管理规定"],
        "judge_logic": "依据网络安全等级保护定级标准及电力行业专项定级要求，核查方案中等保测评及安全防护评估章节的定级内容，结合厂站电力监控系统的业务重要性、数据敏感度、服务范围、安全影响范围等维度，判断系统安全等级定级结果是否匹配系统实际情况，定级依据是否充分、定级流程是否规范，存在定级偏高、偏低、定级无依据等不合理情况即为不合规"
    }
]


@with_session
def add_audit_rule(
    session,
    name: str,
    description: str = "",
    chapter_keywords: list = None,
    judge_logic: str = "",
) -> int:
    """
    新增审计规则，返回自增ID
    """
    if chapter_keywords is None:
        chapter_keywords = []
    m = AuditRuleModel(
        name=name,
        description=description,
        chapter_keywords=chapter_keywords,
        judge_logic=judge_logic,
    )
    session.add(m)
    session.commit()
    return m.id


@with_session
def get_audit_rule_by_id(session, rule_id: int) -> Optional[dict]:
    """
    根据ID获取审计规则，返回字典（避免session关闭后访问属性报错）
    """
    r = session.query(AuditRuleModel).filter_by(id=rule_id).first()
    if r is None:
        return None
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "chapter_keywords": r.chapter_keywords,
        "judge_logic": r.judge_logic,
        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
        "update_time": r.update_time.strftime("%Y-%m-%d %H:%M:%S") if r.update_time else None,
    }


@with_session
def list_audit_rules(
    session,
    limit: int = 100,
    offset: int = 0,
) -> List[dict]:
    """
    获取审计规则列表，按时间倒序
    """
    rules = (
        session.query(AuditRuleModel)
        .order_by(desc(AuditRuleModel.update_time))
        .offset(offset)
        .limit(limit)
        .all()
    )
    data = []
    for r in rules:
        data.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "chapter_keywords": r.chapter_keywords,
            "judge_logic": r.judge_logic,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
            "update_time": r.update_time.strftime("%Y-%m-%d %H:%M:%S") if r.update_time else None,
        })
    return data


@with_session
def update_audit_rule(
    session,
    rule_id: int,
    name: str = None,
    description: str = None,
    chapter_keywords: list = None,
    judge_logic: str = None,
) -> bool:
    """
    更新审计规则（只更新传入的非None字段）
    """
    m = session.query(AuditRuleModel).filter_by(id=rule_id).first()
    if m is None:
        return False
    if name is not None:
        m.name = name
    if description is not None:
        m.description = description
    if chapter_keywords is not None:
        m.chapter_keywords = chapter_keywords
    if judge_logic is not None:
        m.judge_logic = judge_logic
    session.add(m)
    session.commit()
    return True


@with_session
def delete_audit_rule(session, rule_id: int) -> bool:
    """
    删除审计规则
    """
    result = session.query(AuditRuleModel).filter_by(id=rule_id).delete()
    session.commit()
    return result > 0


@with_session
def audit_rule_exists(session, rule_id: int) -> bool:
    """
    检查审计规则是否存在
    """
    return session.query(AuditRuleModel).filter_by(id=rule_id).first() is not None


@with_session
def get_rule_by_name(session, name: str) -> Optional[AuditRuleModel]:
    """
    根据名称查找规则，返回ORM对象（用于内部比较）
    """
    return session.query(AuditRuleModel).filter_by(name=name).first()


@with_session
def init_default_rules(session) -> dict:
    """
    导入默认规则：
    - 如果规则名称已存在且内容完全一致，则跳过
    - 如果规则名称已存在但内容不同，则更新
    - 如果规则名称不存在，则新增

    返回: {"created": int, "updated": int, "skipped": int}
    """
    created = 0
    updated = 0
    skipped = 0

    for rule_data in DEFAULT_AUDIT_RULES:
        existing = session.query(AuditRuleModel).filter_by(name=rule_data["name"]).first()
        if existing:
            # 比较关键字段是否完全一致
            same_desc = (existing.description or "") == (rule_data["description"] or "")
            same_keywords = (existing.chapter_keywords or []) == (rule_data["chapter_keywords"] or [])
            same_logic = (existing.judge_logic or "") == (rule_data["judge_logic"] or "")

            if same_desc and same_keywords and same_logic:
                skipped += 1
            else:
                existing.description = rule_data["description"]
                existing.chapter_keywords = rule_data["chapter_keywords"]
                existing.judge_logic = rule_data["judge_logic"]
                session.add(existing)
                updated += 1
        else:
            m = AuditRuleModel(
                name=rule_data["name"],
                description=rule_data["description"],
                chapter_keywords=rule_data["chapter_keywords"],
                judge_logic=rule_data["judge_logic"],
            )
            session.add(m)
            created += 1

    session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}
