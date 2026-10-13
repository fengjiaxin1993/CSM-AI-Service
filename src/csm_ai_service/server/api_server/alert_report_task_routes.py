"""
预警报告审计任务 API 路由
- 上传文件 → 生成 task_id → 写入 DB → 提交异步队列 → 立即返回 task_id
- 查询任务状态
- 查询任务列表
- 删除任务
"""
import os
from typing import Optional

from fastapi import APIRouter, Query, UploadFile, File, Body

from csm_ai_service.server.db.repository import gen_file_id
from csm_ai_service.server.utils import ApiResponse
from csm_ai_service.server.db.repository.alert_report_task_repository import (
    add_alert_report_task,
    get_alert_report_task_by_id,
    list_alert_report_tasks,
    delete_alert_report_task,
)
from csm_ai_service.server.warning_report_audit.alert_report_task_queue import (
    generate_task_id,
    alert_report_task_worker,
)
from csm_ai_service.server.warning_report_audit.audit.audit_process import (
    save_to_warning_report_file,
    gen_new_filename_by_hash,
)
from csm_ai_service.settings import Settings
from csm_ai_service.utils import build_logger

logger = build_logger()


def _build_task_file_path(task: dict) -> str:
    """按存储规则（{stem}_{content_hash后四位}{ext}）重建任务对应PDF的物理文件路径，供前端预览加载"""
    new_filename = gen_new_filename_by_hash(task.get("file_name", ""), task.get("content_hash", ""))
    return os.path.join(Settings.basic_settings.WARNING_REPORT_DIR, new_filename)


# ==================== 路由定义 ====================

alert_report_task_router = APIRouter(prefix="/api/alert-report-tasks", tags=["告警处置报告审计任务"])


# ==================== 上传文件（异步） ====================

@alert_report_task_router.post("/upload", response_model=ApiResponse)
async def upload_alert_report(file: UploadFile = File(..., description="上传告警处置报告PDF文件")):
    """
    上传告警处置报告文件，生成 task_id，写入数据库，提交异步任务队列，立即返回 task_id。
    同一文件（文件名+内容相同）返回已有的 task_id，不会重复处理。
    """
    try:
        if not file.filename.lower().endswith('.pdf'):
            return ApiResponse(success=False, message="仅支持 PDF 文件上传")

        # 读取文件内容
        file_content = await file.read()
        file_name = file.filename

        # 根据 文件名 + 文件内容 生成 task_id
        task_id = generate_task_id(file_name, file_content)

        # 检查是否已有该任务（去重）
        existing = get_alert_report_task_by_id(task_id)
        if existing:
            return ApiResponse(
                success=True,
                message="文件已存在，返回已有任务",
                data={"task_id": task_id, "status": existing["status"],
                      "file_id": existing["file_id"], "file_name": existing["file_name"],
                      "file_path": _build_task_file_path(existing)},
            )

        # 保存文件到磁盘（同名不同内容时物理文件名会带hash前缀隔离）
        file.file.seek(0)  # 重置指针以便保存
        file_path, content_hash = save_to_warning_report_file(file)
        file_id = gen_file_id(file.filename, content_hash)
        # 写入数据库（file_name存实际落盘的物理文件名，用于任务处理时定位文件）
        add_alert_report_task(task_id=task_id, file_id=file_id, file_name=file.filename, content_hash=content_hash, status="pending")

        # 提交异步任务队列
        alert_report_task_worker.submit_task(task_id)

        return ApiResponse(
            success=True,
            message="文件上传成功，任务已提交",
            data={"task_id": task_id, "status": "pending", "file_path": file_path},
        )
    except Exception as e:
        logger.error(f"上传预警报告失败: {e}")
        return ApiResponse(success=False, message=f"上传失败: {str(e)}")



# ==================== 查询任务状态 ====================

@alert_report_task_router.get("/{task_id}", response_model=ApiResponse)
async def get_alert_report_task(task_id: str):
    """根据 task_id 查询任务状态及结果"""
    try:
        task = get_alert_report_task_by_id(task_id)
        if not task:
            return ApiResponse(success=False, message="任务不存在")
        # 附加物理文件路径（按存储规则重建），供前端加载PDF预览
        task["file_path"] = _build_task_file_path(task)
        return ApiResponse(success=True, message="获取成功", data=task)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


# ==================== 任务列表 ====================

@alert_report_task_router.get("", response_model=ApiResponse)
async def get_all_alert_report_tasks(
    limit: int = Query(100, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    status: str = Query(None, description="状态筛选：pending/pdf_processing/pdf_done/audit_processing/completed/failed"),
):
    """查看所有预警报告审计任务列表"""
    try:
        tasks = list_alert_report_tasks(limit=limit, offset=offset, status=status)
        return ApiResponse(
            success=True,
            message="获取成功",
            data={"tasks": tasks, "total": len(tasks)},
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"获取任务列表失败: {str(e)}")


# ==================== 删除任务 ====================

@alert_report_task_router.post("/delete/{task_id}", response_model=ApiResponse)
async def remove_alert_report_task(task_id: str):
    """删除指定任务"""
    try:
        task = get_alert_report_task_by_id(task_id)
        if not task:
            return ApiResponse(success=False, message="任务不存在")
        success = delete_alert_report_task(task_id)
        if success:
            return ApiResponse(success=True, message="任务已删除", data={"task_id": task_id})
        return ApiResponse(success=False, message="删除任务失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"删除失败: {str(e)}")
