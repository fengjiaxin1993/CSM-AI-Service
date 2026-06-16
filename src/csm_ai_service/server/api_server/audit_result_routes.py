"""
审计结果 API 路由
"""
from fastapi import APIRouter

from csm_ai_service.server.utils import ApiResponse
from csm_ai_service.server.db.repository.audit_result_repository import get_audit_results_by_task_id

# ==================== 路由定义 ====================
audit_result_router = APIRouter(prefix="/api/audit-results", tags=["审计结果管理"])


@audit_result_router.get("/task/{task_id}", response_model=ApiResponse)
async def get_results_by_task(task_id: int):
    """查询 task_id 对应的所有审计结果"""
    try:
        results = get_audit_results_by_task_id(task_id)
        if not results:
            return ApiResponse(success=False, message="未找到该任务的审计结果")

        pass_count = sum(1 for r in results if r.is_compliant is True)
        fail_count = sum(1 for r in results if r.is_compliant is False)

        return ApiResponse(
            success=True,
            message="获取成功",
            data={
                "total": len(results),
                "pass": pass_count,
                "fail": fail_count,
                "results": results,
            }
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")
