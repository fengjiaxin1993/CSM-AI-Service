"""
测试 OCR / 合同 / 任务 / 审计结果 全流程接口
执行顺序严格，前序步骤的数据通过全局变量传递给后续步骤
"""
import asyncio
import json
import os
import httpx
import pytest

from test_api.pytest.config import BASE
PDF_NAME = "页面提取自－草台第一分散式电站电力监控系统二次安全防护实施方案.pdf"
PDF_PATH = os.path.join(os.path.dirname(__file__),"data", PDF_NAME)
# ==================== 全局变量 ====================
_contract_id = None
_task_id = None
_file_path = None
_file_name = None


# ==================== 1. 上传合同 ====================

@pytest.mark.asyncio
@pytest.mark.order(1)
async def test_upload_contract_with_pdf():
    """上传合同PDF文件，保存 contract_id / task_id / file_path"""
    global _contract_id, _task_id, _file_path, _file_name
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(PDF_PATH, "rb") as f:
            r = await c.post(
                "/api/upload",
                files={"file": (PDF_NAME, f, "application/pdf")},
            )
    assert r.status_code == 200
    resp = r.json()
    print(f"[upload_contract_with_pdf] 响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    assert resp.get("success"), f"上传失败: {resp.get('message')}"
    data = resp["data"]
    _contract_id = data["contract_id"]
    _task_id = data["task_id"]
    _file_path = data.get("file_path", "")
    _file_name = data.get("file_name", "")
    print(f"[upload_contract_with_pdf] contract_id={_contract_id}, task_id={_task_id}, file_path={_file_path}")


# ==================== 2. PDF 页面信息 ====================

@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_pdf_pages():
    """获取PDF页面信息"""
    if not _file_path:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        r = await c.post("/api/pdf_pages", json={"filepath": _file_path})
    assert r.status_code == 200
    resp = r.json()
    total = resp.get("total_pages", 0)
    print(f"[pdf_pages] 总页数: {total}, success: {resp.get('success')}")


# ==================== 3. 轮询任务状态 ====================

@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_task_status_polling():
    """轮询任务状态，直到 completed 或 failed"""
    if not _task_id:
        pytest.skip("前置上传失败，跳过")

    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        max_attempts = 60
        for i in range(max_attempts):
            r = await c.get(f"/api/task/status/{_task_id}")
            assert r.status_code == 200
            resp = r.json()
            status = resp.get("data", {}).get("status", "unknown")
            print(f"[task_status_polling] 第{i+1}次查询: status={status}")
            if status in ("completed", "failed"):
                print(f"[task_status_polling] 任务最终状态: {status}")
                break
            await asyncio.sleep(10)
        else:
            pytest.fail(f"任务在 {max_attempts * 5}s 内未完成，最终状态: {status}")


# ==================== 4. 获取审计结果 ====================

@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_get_audit_result():
    """获取审计结果（合同字段提取）"""
    if not _contract_id:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/api/get_audit_result", json={
            "contract_id": _contract_id,
            "task_id": _task_id,
        })
    assert r.status_code == 200
    resp = r.json()
    print(f"[get_audit_result] success: {resp.get('success')}, 字段数: {len(resp.get('check_info', []))}")


# ==================== 5. 审计结果查询 ====================

@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_get_audit_results_by_task():
    """根据 task_id 查询审计结果"""
    if not _task_id:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get(f"/api/audit-results/task/{_task_id}")
    assert r.status_code == 200
    resp = r.json()
    print(f"[get_audit_results_by_task] 响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_get_audit_results_not_found():
    """查询不存在的 task_id 审计结果"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/api/audit-results/task/99999")
    assert r.status_code == 200
    print(f"[get_audit_results_not_found] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


# ==================== 6. 合同管理 ====================

@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_list_contracts():
    """获取合同列表"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/api/contracts/list")
    assert r.status_code == 200
    resp = r.json()
    total = resp.get("data", {}).get("total", 0)
    print(f"[list_contracts] 合同总数: {total}")


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_list_contracts_with_pagination():
    """获取合同列表（带分页）"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/api/contracts/list", params={"limit": 5, "offset": 0})
    assert r.status_code == 200
    print(f"[list_contracts_with_pagination] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_get_contract_detail():
    """查询刚上传的合同详情"""
    if not _contract_id:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get(f"/api/contracts/detail/{_contract_id}")
    assert r.status_code == 200
    print(f"[get_contract_detail] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_get_contract_detail_not_found():
    """查询不存在的合同"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/api/contracts/detail/99999")
    assert r.status_code == 200
    print(f"[get_contract_detail_not_found] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_delete_contract_not_found():
    """删除不存在的合同"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/api/contracts/delete/99999")
    assert r.status_code == 200
    print(f"[delete_contract_not_found] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


# ==================== 7. 任务管理 ====================

@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_list_tasks():
    """查看任务列表"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/api/tasks")
    assert r.status_code == 200
    resp = r.json()
    total = resp.get("data", {}).get("total", 0)
    print(f"[list_tasks] 任务总数: {total}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_list_tasks_with_pagination():
    """查看任务列表（带分页）"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/api/tasks", params={"limit": 5, "offset": 0})
    assert r.status_code == 200
    print(f"[list_tasks_with_pagination] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_get_task():
    """查询刚创建的任务"""
    if not _task_id:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get(f"/api/tasks/{_task_id}")
    assert r.status_code == 200
    print(f"[get_task] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_get_task_by_contract():
    """查询合同对应的任务"""
    if not _contract_id:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get(f"/api/tasks/contract/{_contract_id}")
    assert r.status_code == 200
    print(f"[get_task_by_contract] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_get_task_not_found():
    """查询不存在的任务"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/api/tasks/99999")
    assert r.status_code == 200
    print(f"[get_task_not_found] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_reprocess_contract_not_found():
    """重新处理不存在的合同"""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/api/tasks/reprocess/99999")
    assert r.status_code == 200
    print(f"[reprocess_contract_not_found] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


# ==================== 8. 清理：删除任务与合同 ====================

@pytest.mark.asyncio
@pytest.mark.order(8)
async def test_delete_task():
    """删除刚创建的任务"""
    if not _task_id:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post(f"/api/tasks/delete/{_task_id}")
    assert r.status_code == 200
    print(f"[delete_task] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(9)
async def test_delete_contract():
    """删除刚上传的合同"""
    if not _contract_id:
        pytest.skip("前置上传失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post(f"/api/contracts/delete/{_contract_id}")
    assert r.status_code == 200
    print(f"[delete_contract] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
