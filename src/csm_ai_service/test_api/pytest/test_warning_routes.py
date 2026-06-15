"""测试 /warning 接口"""
import os
import httpx
import pytest

BASE = "http://127.0.0.1:7861"
DOCX_NAME = "关于110kVXX变告警说明.docx"
DOCX_PATH = os.path.join(os.path.dirname(__file__), DOCX_NAME)


@pytest.mark.asyncio
async def test_warning_analyze():
    assert os.path.exists(DOCX_PATH), f"测试文件不存在: {DOCX_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(DOCX_PATH, "rb") as f:
            files = {"file": (DOCX_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_001"}
            r = await c.post("/warning/analyze", files=files, data=data)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_generate_notice_doc():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/warning/generate_notice_doc", json={
            "notice_no": "WLAQ2026021001",
            "receive": "湖北宜昌地调",
            "editor": "张三",
            "auditor": "李四",
            "warning_time": "2026年02月03日",
            "warning_unit": "宜昌地调网安平台",
            "monitor_device": "监测装置",
            "warning_level": "紧急",
            "latest_time": "2026-02-03 14:28:36",
            "device_ip": "192.168.100.23",
            "content": "未授权访问风险",
            "reason_analysis": "安全意识不足",
            "disposal_suggest": "1. 关闭高危端口",
            "deadline": "2026年02月20日",
            "contact_tel": "027-8866XXXX",
            "cur_date": "2026年02月01日"
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_save_warning_report():
    assert os.path.exists(DOCX_PATH), f"测试文件不存在: {DOCX_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(DOCX_PATH, "rb") as f:
            files = {"file": (DOCX_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_save_001"}
            r = await c.post("/warning/save_warning_report", files=files, data=data)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_warning_report():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/warning/delete_warning_report", json="warning_save_001")
    assert r.status_code == 200
