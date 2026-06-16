"""
合同管理 API 路由
提供合同的增删改查及文件上传接口
"""
import os
from fastapi import APIRouter, Query

from csm_ai_service.server.utils import ApiResponse
from csm_ai_service.server.db.repository.contract_repository import (
    get_contract_by_id,
    list_contracts,
    delete_contract,
)
from csm_ai_service.settings import Settings
from csm_ai_service.server.protection_audit.common.file_tools import delete_ocr_cache

# ==================== 路由定义 ====================
contract_router = APIRouter(prefix="/api/contracts", tags=["合同管理"])


def _get_contract_file_path(file_name: str) -> str:
    """根据文件名拼接上传文件的完整路径"""
    return os.path.join(Settings.basic_settings.UPLOADS_DIR, file_name)


@contract_router.get("/list", response_model=ApiResponse)
async def get_contracts(
        limit: int = Query(100, description="返回数量限制"),
        offset: int = Query(0, description="偏移量"),
):
    """获取合同列表"""
    try:
        contracts = list_contracts(limit=limit, offset=offset)
        return ApiResponse(success=True, message="获取成功", data={"contracts": contracts, "total": len(contracts)})
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@contract_router.get("/detail/{contract_id}", response_model=ApiResponse)
async def get_contract_detail(contract_id: int):
    """获取单个合同详情"""
    try:
        contract = get_contract_by_id(contract_id)
        if not contract:
            return ApiResponse(success=False, message="合同不存在")
        return ApiResponse(success=True, message="获取成功", data=contract)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")



@contract_router.post("/delete/{contract_id}", response_model=ApiResponse)
async def remove_contract(contract_id: int):
    """
    删除合同（同时删除上传文件、OCR缓存目录和数据库记录）
    文件删除失败（如被占用）不阻断数据库记录的删除。
    """
    warnings = []
    try:
        contract = get_contract_by_id(contract_id)
        if contract:
            # 删除上传的 PDF 文件（通过 file_name 拼接路径）
            file_path = _get_contract_file_path(contract["file_name"])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    warnings.append(f"文件删除失败(可能被占用): {e}")

            # 删除 OCR 缓存目录
            try:
                delete_ocr_cache(contract_id)
            except OSError as e:
                warnings.append(f"缓存删除失败: {e}")

        success = delete_contract(contract_id)
        if success:
            msg = "合同删除成功"
            if warnings:
                msg += "，" + "；".join(warnings)
            return ApiResponse(success=True, message=msg)
        return ApiResponse(success=False, message="合同不存在或删除失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"删除失败: {str(e)}")