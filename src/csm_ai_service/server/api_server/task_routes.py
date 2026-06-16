"""
任务管理 API 路由
"""
import os
from fastapi import APIRouter, Query

from csm_ai_service.server.api_server.contract_routes import _get_contract_file_path
from csm_ai_service.server.utils import ApiResponse
from csm_ai_service.server.db.repository.audit_result_repository import delete_audit_results_by_task_id
from csm_ai_service.server.db.repository.contract_repository import get_contract_by_id
from csm_ai_service.server.db.repository.task_repository import (
    add_task,
    get_task_by_id,
    get_task_by_contract_id,
    list_tasks,
    delete_task,
)
from csm_ai_service.server.protection_audit.task_queue import task_worker


# ==================== 路由定义 ====================
task_router = APIRouter(prefix="/api/tasks", tags=["任务管理"])


# ==================== 任务查询 ====================

@task_router.get("/contract/{contract_id}", response_model=ApiResponse)
async def get_task_by_contract(contract_id: int):
    """获取合同对应的任务详情"""
    try:
        task = get_task_by_contract_id(contract_id)
        if not task:
            return ApiResponse(success=False, message="未找到该合同的任务记录")
        return ApiResponse(success=True, message="获取成功", data=task)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@task_router.get("/{task_id}", response_model=ApiResponse)
async def get_task(task_id: int):
    """根据任务ID查询任务状态"""
    try:
        task = get_task_by_id(task_id)
        if not task:
            return ApiResponse(success=False, message="任务不存在")
        return ApiResponse(success=True, message="获取成功", data=task)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@task_router.get("", response_model=ApiResponse)
async def get_all_tasks(
    limit: int = Query(100, description="返回数量限制"),
    offset: int = Query(0, description="偏移量"),
):
    """查看所有任务列表"""
    try:
        tasks = list_tasks(limit=limit, offset=offset)
        return ApiResponse(
            success=True,
            message="获取成功",
            data={"tasks": tasks, "total": len(tasks)}
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"获取任务列表失败: {str(e)}")


# ==================== 任务操作 ====================

@task_router.post("/delete/{task_id}", response_model=ApiResponse)
async def remove_task(task_id: int):
    """删除指定任务及其关联的审计结果"""
    try:
        task = get_task_by_id(task_id)
        if not task:
            return ApiResponse(success=False, message="任务不存在")

        deleted_results = delete_audit_results_by_task_id(task_id)
        success = delete_task(task_id)
        if success:
            return ApiResponse(
                success=True,
                message=f"任务已删除，同时删除了 {deleted_results} 条审计结果",
                data={"task_id": task_id, "deleted_results": deleted_results}
            )
        return ApiResponse(success=False, message="删除任务失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"删除失败: {str(e)}")


@task_router.post("/reprocess/{contract_id}", response_model=ApiResponse)
async def reprocess_contract(contract_id: int):
    """重新处理合同（重新提交到任务队列执行 OCR + 审计）"""
    try:
        contract = get_contract_by_id(contract_id)
        if not contract:
            return ApiResponse(success=False, message="合同不存在")

        file_path = _get_contract_file_path(contract["file_name"])
        if not os.path.exists(file_path):
            return ApiResponse(success=False, message="合同文件不存在")

        task_id = add_task(contract_id=contract_id, status="pending")
        task_worker.submit_task(task_id)

        return ApiResponse(
            success=True,
            message="已重新提交任务",
            data={"contract_id": contract_id, "task_id": task_id}
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"重新处理失败: {str(e)}")
