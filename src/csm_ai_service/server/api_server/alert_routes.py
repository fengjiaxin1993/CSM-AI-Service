"""
历史告警处置报告 & 告警处置规则库 API 路由
提供增删改查及全文检索接口
"""
import io
from typing import List

from fastapi import APIRouter, Query, UploadFile, File
from fastapi.responses import StreamingResponse

from csm_ai_service.server.utils import ApiResponse, AlertReport, AlertRule
from csm_ai_service.server.db.repository.alert_repository import (
    add_alert_report, get_alert_report_by_id, list_alert_reports,
    update_alert_report, delete_alert_report, search_alert_reports,
    confirm_alert_report,
    add_alert_rule, get_alert_rule_by_id, list_alert_rules,
    update_alert_rule, delete_alert_rule, search_alert_rules,
    init_default_alert_rules,
    export_alert_reports_to_excel, import_alert_reports_from_excel,
    export_alert_rules_to_excel, import_alert_rules_from_excel,
)
from csm_ai_service.server.csm_analyze.warning_analysis.report_analyze import save_warning_report_only_by_file, save_warning_report

# ==================== 告警报告路由 ====================

alert_report_router = APIRouter(prefix="/api/alert-reports", tags=["告警处置报告"])


@alert_report_router.post("/create", response_model=ApiResponse)
async def create_alert_report(report: AlertReport):
    """创建告警处置报告（默认status=cache缓存状态）"""
    try:
        report_id = add_alert_report(
            report_title=report.report_title,
            file_name=report.file_name,
            alert_content=report.alert_content,
            meta_info=report.meta_info,
            full_text=report.full_text,
            table_data_text=report.table_data_text,
            status=report.status or "cache",
        )
        return ApiResponse(success=True, message="创建成功", data={"id": report_id})
    except ValueError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"创建失败: {str(e)}")



alert_report_router.post(
    "/upload",
    summary="保存告警处置报告",
)(save_warning_report_only_by_file)


@alert_report_router.post("/batch-upload", response_model=ApiResponse)
async def batch_upload_alert_reports(files: List[UploadFile] = File(..., description="批量上传文件")):
    """批量上传告警处置报告，逐个调用单文件上传逻辑，返回汇总结果"""
    from csm_ai_service.server.utils import BaseResponse

    success_count = 0
    fail_count = 0
    details = []

    for i, file in enumerate(files):
        try:
            result = save_warning_report(file=file)
            if result.code == 200:
                success_count += 1
                details.append({"file": file.filename, "status": "success", "message": result.msg})
            else:
                fail_count += 1
                details.append({"file": file.filename, "status": "fail", "message": result.msg})
        except Exception as e:
            fail_count += 1
            details.append({"file": file.filename, "status": "fail", "message": str(e)})

    return ApiResponse(
        success=True,
        message=f"批量上传完成：成功 {success_count} 个，失败 {fail_count} 个",
        data={
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(files),
            "details": details,
        },
    )



@alert_report_router.get("/list", response_model=ApiResponse)
async def get_alert_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str = Query(None, description="状态筛选：cache/saved，不传则返回全部"),
):
    """获取告警报告列表，可按status筛选"""
    try:
        reports = list_alert_reports(
            limit=limit, offset=offset, status=status,
        )
        return ApiResponse(success=True, message="获取成功", data={"reports": reports, "total": len(reports)})
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@alert_report_router.get("/detail/{report_id}", response_model=ApiResponse)
async def get_alert_report_detail(report_id: int):
    """获取告警报告详情"""
    try:
        data = get_alert_report_by_id(report_id)
        if not data:
            return ApiResponse(success=False, message="报告不存在")
        return ApiResponse(success=True, message="获取成功", data=data)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@alert_report_router.post("/update/{report_id}", response_model=ApiResponse)
async def modify_alert_report(report_id: int, report: AlertReport):
    """更新告警报告"""
    try:
        success = update_alert_report(
            report_id=report_id,
            report_title=report.report_title,
            file_name=report.file_name,
            alert_content=report.alert_content,
            meta_info=report.meta_info,
            full_text=report.full_text,
            table_data_text=report.table_data_text,
            status=report.status,
        )
        if success:
            return ApiResponse(success=True, message="更新成功")
        return ApiResponse(success=False, message="报告不存在或更新失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"更新失败: {str(e)}")


@alert_report_router.post("/confirm/{report_id}", response_model=ApiResponse)
async def confirm_alert_report_api(report_id: int):
    """确认保存告警报告（将status从cache改为saved）"""
    try:
        success = confirm_alert_report(report_id=report_id)
        if success:
            return ApiResponse(success=True, message="确认保存成功")
        return ApiResponse(success=False, message="报告不存在或确认失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"确认失败: {str(e)}")


@alert_report_router.post("/delete/{report_id}", response_model=ApiResponse)
async def remove_alert_report(report_id: int):
    """删除告警报告"""
    try:
        success = delete_alert_report(report_id)
        if success:
            return ApiResponse(success=True, message="删除成功")
        return ApiResponse(success=False, message="报告不存在或删除失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"删除失败: {str(e)}")


@alert_report_router.get("/search", response_model=ApiResponse)
async def search_alert_reports_api(
    query: str = Query(..., description="检索关键词"),
    top_k: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """全文检索告警报告（基于jieba分词）"""
    try:
        results = search_alert_reports(query=query, top_k=top_k)
        return ApiResponse(success=True, message="检索完成", data={"results": results, "total": len(results)})
    except Exception as e:
        return ApiResponse(success=False, message=f"检索失败: {str(e)}")


@alert_report_router.get("/export-excel")
async def export_alert_reports_excel():
    """导出所有告警处置报告为Excel文件"""
    try:
        file_bytes = export_alert_reports_to_excel()
        buf = io.BytesIO(file_bytes)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=alert_reports.xlsx"},
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"导出失败: {str(e)}")


@alert_report_router.post("/import-excel", response_model=ApiResponse)
async def import_alert_reports_excel(file: UploadFile = File(...)):
    """从Excel文件导入告警处置报告"""
    try:
        file_bytes = await file.read()
        if not file.filename.endswith((".xlsx", ".xls")):
            return ApiResponse(success=False, message="仅支持 .xlsx / .xls 格式文件")
        result = import_alert_reports_from_excel(file_bytes=file_bytes)
        return ApiResponse(
            success=True,
            message=f"导入完成：新增 {result['inserted']} 条，跳过 {result['skipped']} 条",
            data=result,
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"导入失败: {str(e)}")


# ==================== 告警规则路由 ====================

alert_rule_router = APIRouter(prefix="/api/alert-rules", tags=["告警处置规则"])


@alert_rule_router.post("/create", response_model=ApiResponse)
async def create_alert_rule(rule: AlertRule):
    """创建告警处置规则"""
    try:
        rule_id = add_alert_rule(
            rule_code=rule.rule_code,
            name=rule.name,
            description=rule.description,
        )
        return ApiResponse(success=True, message="创建成功", data={"id": rule_id})
    except Exception as e:
        return ApiResponse(success=False, message=f"创建失败: {str(e)}")


@alert_rule_router.get("/list", response_model=ApiResponse)
async def get_alert_rules(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取告警规则列表"""
    try:
        rules = list_alert_rules(limit=limit, offset=offset)
        return ApiResponse(success=True, message="获取成功", data={"rules": rules, "total": len(rules)})
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@alert_rule_router.get("/detail/{rule_id}", response_model=ApiResponse)
async def get_alert_rule_detail(rule_id: int):
    """获取告警规则详情"""
    try:
        data = get_alert_rule_by_id(rule_id)
        if not data:
            return ApiResponse(success=False, message="规则不存在")
        return ApiResponse(success=True, message="获取成功", data=data)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取失败: {str(e)}")


@alert_rule_router.post("/update/{rule_id}", response_model=ApiResponse)
async def modify_alert_rule(rule_id: int, rule: AlertRule):
    """更新告警规则"""
    try:
        success = update_alert_rule(
            rule_id=rule_id,
            rule_code=rule.rule_code,
            name=rule.name,
            description=rule.description,
        )
        if success:
            return ApiResponse(success=True, message="更新成功")
        return ApiResponse(success=False, message="规则不存在或更新失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"更新失败: {str(e)}")


@alert_rule_router.post("/delete/{rule_id}", response_model=ApiResponse)
async def remove_alert_rule(rule_id: int):
    """删除告警规则"""
    try:
        success = delete_alert_rule(rule_id)
        if success:
            return ApiResponse(success=True, message="删除成功")
        return ApiResponse(success=False, message="规则不存在或删除失败")
    except Exception as e:
        return ApiResponse(success=False, message=f"删除失败: {str(e)}")


@alert_rule_router.get("/search", response_model=ApiResponse)
async def search_alert_rules_api(
    query: str = Query(..., description="检索关键词"),
    top_k: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """全文检索告警规则（基于jieba分词）"""
    try:
        results = search_alert_rules(query=query, top_k=top_k)
        return ApiResponse(success=True, message="检索完成", data={"results": results, "total": len(results)})
    except Exception as e:
        return ApiResponse(success=False, message=f"检索失败: {str(e)}")


@alert_rule_router.post("/init-default", response_model=ApiResponse)
async def init_default_rules():
    """初始化默认告警处置规则（已存在的规则不会重复插入）"""
    try:
        inserted_ids = init_default_alert_rules()
        return ApiResponse(success=True, message="初始化完成", data={"inserted_ids": inserted_ids, "inserted_count": len(inserted_ids)})
    except Exception as e:
        return ApiResponse(success=False, message=f"初始化失败: {str(e)}")


@alert_rule_router.get("/export-excel")
async def export_alert_rules_excel():
    """导出所有告警处置规则为Excel文件"""
    try:
        file_bytes = export_alert_rules_to_excel()
        buf = io.BytesIO(file_bytes)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=alert_rules.xlsx"},
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"导出失败: {str(e)}")


@alert_rule_router.post("/import-excel", response_model=ApiResponse)
async def import_alert_rules_excel(file: UploadFile = File(...)):
    """从Excel文件导入告警处置规则"""
    try:
        file_bytes = await file.read()
        if not file.filename.endswith((".xlsx", ".xls")):
            return ApiResponse(success=False, message="仅支持 .xlsx / .xls 格式文件")
        result = import_alert_rules_from_excel(file_bytes=file_bytes)
        return ApiResponse(
            success=True,
            message=f"导入完成：新增 {result['inserted']} 条，跳过 {result['skipped']} 条",
            data=result,
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"导入失败: {str(e)}")
