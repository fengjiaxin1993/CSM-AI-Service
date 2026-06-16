import os
import shutil
from typing import Optional
from fastapi import APIRouter, Body, UploadFile, File
from csm_ai_service.server.utils import ApiResponse
from csm_ai_service.server.protection_audit.audit.extract_audit import get_audit_fields_from_db
from csm_ai_service.server.protection_audit.tools.file_tools import ensure_cache_dir
from csm_ai_service.server.protection_audit.tools.pdf_tools import get_pdf_pages
from csm_ai_service.server.protection_audit.task_queue import task_worker
from csm_ai_service.settings import Settings
from csm_ai_service.server.db.repository.contract_repository import get_contract_by_name, add_contract
from csm_ai_service.server.db.repository.task_repository import get_task_by_id, add_task

ocr_router = APIRouter(prefix="/api", tags=["OCR文件识别"])

@ocr_router.post("/pdf_pages")
async def pdf_pages(
        filepath: Optional[str] = Body(None, embed=True, description="文件路径")): 
    """
    获取PDF页面信息（包含图像Base64）

    - **filepath**: PDF文件路径
    - **zoom_factor**: 缩放因子（默认1.0）

    返回:
    - **success**: 是否成功
    - **pages**: 页面列表
    - **total_pages**: 总页数
    """
    if not filepath:
        return {"success": False, "error": "文件路径为空", "pages": []}
    return get_pdf_pages(filepath, 1.0)



@ocr_router.post("/upload", response_model=ApiResponse)
async def upload_contract(
        file: UploadFile = File(..., description="合同文件(PDF)")
):
    """
    上传合同文件
    1. 保存文件到本地
    2. 创建数据库记录
    3. 创建任务记录（含规则关联）并提交到队列
    4. 立即返回 task_id 和 contract_id

    任务在后台依次执行 OCR识别 -> 审计，可通过 /api/contracts/task/{contract_id} 查询进度
    """
    try:
        if not file.filename.lower().endswith('.pdf'):
            return ApiResponse(success=False, message="仅支持 PDF 文件上传")

        # 检查数据库中是否已存在同名文件
        existing = get_contract_by_name(file.filename)
        if existing:
            existing_contract_id = existing["id"]
            # 确保缓存目录存在并复制原始文件
            cache_dir = ensure_cache_dir(existing_contract_id)
            src_path = os.path.join(Settings.basic_settings.UPLOADS_DIR, file.filename)
            dst_path = os.path.join(cache_dir, file.filename)
            if os.path.exists(src_path) and not os.path.exists(dst_path):
                shutil.copy2(src_path, dst_path)
            task_id = add_task(
                contract_id=existing_contract_id,
                status="pending",
            )
            task_worker.submit_task(task_id)
            return ApiResponse(
                success=True,
                message="文件已存在，已重新提交任务",
                data={
                    "contract_id": existing_contract_id,
                    "task_id": task_id,
                    "file_name": file.filename,
                    "file_path": dst_path,
                    "status": "pending",
                    "existed": True,
                }
            )

        # 不在数据库中

        filename = file.filename
        filepath = os.path.join(Settings.basic_settings.UPLOADS_DIR, filename)
        if not os.path.exists(filepath):
            content = await file.read()
            with open(filepath, "wb") as f:
                f.write(content)

        file_size = os.path.getsize(filepath)

        # 创建数据库记录（数据库只存 file_name，不存路径）
        contract_id = add_contract(
            file_name=filename,
            file_size=file_size,
            file_type="pdf",
            status="pending",
        )

        # 创建合同缓存目录，并将原始文件复制到缓存目录
        cache_dir = ensure_cache_dir(contract_id)
        dst_path = os.path.join(cache_dir, filename)
        if os.path.exists(filepath) and not os.path.exists(dst_path):
            shutil.copy2(filepath, dst_path)

        task_id = add_task(
            contract_id=contract_id,
            status="pending",
        )
        task_worker.submit_task(task_id)

        print(f"[Upload] 合同 {contract_id} 已提交，任务ID: {task_id}")

        return ApiResponse(
            success=True,
            message="文件上传成功，已提交到处理队列",
            data={
                "contract_id": contract_id,
                "task_id": task_id,
                "file_name": filename,
                "file_path": dst_path,
                "file_size": file_size,
                "status": "pending",
                "existed": False,
            }
        )

    except Exception as e:
        return ApiResponse(success=False, message=f"上传失败: {str(e)}")


@ocr_router.get("/task/status/{task_id}", response_model=ApiResponse)
async def get_task_status(task_id: int):
    """
    查询任务状态

    - **task_id**: 任务ID

    返回:
    - **success**: 是否成功
    - **data**: {"status": "pending/processing/completed/failed"}
    """
    try:
        task = get_task_by_id(task_id)
        if not task:
            return ApiResponse(success=False, message="任务不存在")
        return ApiResponse(success=True, message="获取成功", data={"status": task.get("status")})
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@ocr_router.post("/get_audit_result")
async def get_audit_results(
        contract_id: int = Body(0, embed=True, description="合同ID"),
        task_id: int = Body(0, embed=True, description="任务ID")
):
    """
    提取合同关键字段（带精确定位）

    - **filepath**: PDF文件路径

    返回:
    - **success**: 是否成功
    - **extract_info**: 提取的字段信息
    - **field_positions**: 字段位置信息（用于前端定位）
    """

    # 调用合同字段提取函数
    result = get_audit_fields_from_db(contract_id, task_id)
    # 转换位置信息为前端格式
    field_positions = result.get("field_positions", {})
    formatted_positions = {}

    for field_name, positions in field_positions.items():
        formatted_positions[field_name] = []
        for pos in positions:
            formatted_positions[field_name].append({
                "page_num": pos.get("page_num", pos.get("layout_idx", 0)),
                "bbox": pos.get("block_bbox", []),
                "content": pos.get("block_content", "")[:100],
                "match_type": pos.get("match_type", "unknown")
            })

    return {
        "success": True,
        "check_info": result.get("check_info", []),
        "field_positions": formatted_positions
    }


