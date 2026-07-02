"""
审计规则管理 API 路由
提供规则的增删改查接口
"""
from fastapi import APIRouter

from csm_ai_service.server.db.repository import (
    add_audit_rule,
    get_audit_rule_by_id,
    list_audit_rules,
    update_audit_rule,
    delete_audit_rule,
    init_default_rules,
)
from csm_ai_service.server.utils import ApiResponse, AuditRuleCreate, AuditRuleUpdate

# ==================== Pydantic 模型 ====================




# ==================== 路由定义 ====================
audit_rule_router = APIRouter(prefix="/api/rules", tags=["审计规则管理"])


@audit_rule_router.post("/create", response_model=ApiResponse)
async def create_rule(rule: AuditRuleCreate):
    """
    创建新规则
    """
    try:
        rule_id = add_audit_rule(
            name=rule.name,
            description=rule.description,
            chapter_keywords=rule.chapter_keywords,
            judge_logic=rule.judge_logic,
            is_enabled=rule.is_enabled,
        )
        return ApiResponse(success=True, message="规则创建成功", data={"id": rule_id})
    except Exception as e:
        return ApiResponse(success=False, message=f"创建失败: {str(e)}")


@audit_rule_router.get("/list", response_model=ApiResponse)
async def get_rules():
    """
    获取规则列表
    """
    try:
        rules = list_audit_rules()
        return ApiResponse(success=True, message="获取成功", data={"rules": rules, "total": len(rules)})
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@audit_rule_router.get("/detail/{rule_id}", response_model=ApiResponse)
async def get_rule_detail(rule_id: int):
    """
    获取单个规则详情
    """
    try:
        data = get_audit_rule_by_id(rule_id)
        if not data:
            return ApiResponse(success=False, message="规则不存在")
        return ApiResponse(success=True, message="获取成功", data=data)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@audit_rule_router.post("/update/{rule_id}", response_model=ApiResponse)
async def modify_rule(rule_id: int, rule: AuditRuleUpdate):
    """
    更新规则
    """
    try:
        success = update_audit_rule(
            rule_id=rule_id,
            name=rule.name,
            description=rule.description,
            chapter_keywords=rule.chapter_keywords,
            judge_logic=rule.judge_logic,
            is_enabled=rule.is_enabled,
        )
        if success:
            return ApiResponse(success=True, message="规则更新成功")
        return ApiResponse(success=False, message="规则不存在或更新失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"更新失败: {str(e)}")


@audit_rule_router.post("/delete/{rule_id}", response_model=ApiResponse)
async def remove_rule(rule_id: int):
    """
    删除规则
    """
    try:
        success = delete_audit_rule(rule_id)
        if success:
            return ApiResponse(success=True, message="规则删除成功")
        return ApiResponse(success=False, message="规则不存在或删除失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"删除失败: {str(e)}")


@audit_rule_router.post("/init_default", response_model=ApiResponse)
async def init_default():
    """
    导入默认规则：
    - 名称相同且内容完全一致则跳过
    - 名称相同但内容不同则更新
    - 名称不存在则新增
    """
    try:
        result = init_default_rules()
        msg_parts = []
        if result["created"] > 0:
            msg_parts.append(f"新增 {result['created']} 条")
        if result["updated"] > 0:
            msg_parts.append(f"更新 {result['updated']} 条")
        if result["skipped"] > 0:
            msg_parts.append(f"跳过 {result['skipped']} 条（内容一致）")
        if not msg_parts:
            msg_parts.append("无变化")
        return ApiResponse(
            success=True,
            message="初始化完成: " + "，".join(msg_parts),
            data=result,
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"初始化失败: {str(e)}")
