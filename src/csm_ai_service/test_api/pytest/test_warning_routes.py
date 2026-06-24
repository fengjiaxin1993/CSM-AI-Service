"""测试 /warning 接口"""
import json
import os
import httpx
import pytest

import yaml

# 从 YAML 配置文件读取测试服务地址
_config_path = "test_config.yaml"
with open(_config_path, "r", encoding="utf-8") as f:
    _config = yaml.safe_load(f)

BASE = _config["server"]["base_url"]
TIMEOUT = _config["server"].get("timeout", 120)
DOCX_NAME = "关于110kVXX变告警说明.docx"
DOCX_PATH = os.path.join(os.path.dirname(__file__),"data", DOCX_NAME)

PDF_NAME = "pdf-告警分析报告模板 -demo.pdf"
PDF_PATH = os.path.join(os.path.dirname(__file__),"data", PDF_NAME)

JPG_NAME = "告警处置报告-demo-图片版.pdf"
JPG_PATH = os.path.join(os.path.dirname(__file__),"data", JPG_NAME)


@pytest.mark.asyncio
@pytest.mark.order(1)
async def test_warning_analyze1():
    assert os.path.exists(DOCX_PATH), f"测试文件不存在: {DOCX_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(DOCX_PATH, "rb") as f:
            files = {"file": (DOCX_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_001"}
            r = await c.post("/warning/analyze", files=files, data=data)
    assert r.status_code == 200
    print(f"[warning_analyze] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")



@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_save_warning_report1():
    assert os.path.exists(DOCX_PATH), f"测试文件不存在: {DOCX_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(DOCX_PATH, "rb") as f:
            files = {"file": (DOCX_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_001"}
            r = await c.post("/warning/save_warning_report", files=files, data=data)
    assert r.status_code == 200
    print(f"[save_warning_report] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_delete_warning_report1():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/warning/delete_warning_report", json="warning_001")
    assert r.status_code == 200
    print(f"[delete_warning_report] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_warning_analyze2():
    assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(PDF_PATH, "rb") as f:
            files = {"file": (PDF_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_002"}
            r = await c.post("/warning/analyze", files=files, data=data)
    assert r.status_code == 200
    print(f"[warning_analyze] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")



@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_save_warning_report2():
    assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(PDF_PATH, "rb") as f:
            files = {"file": (DOCX_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_002"}
            r = await c.post("/warning/save_warning_report", files=files, data=data)
    assert r.status_code == 200
    print(f"[save_warning_report] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_delete_warning_report2():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/warning/delete_warning_report", json="warning_002")
    assert r.status_code == 200
    print(f"[delete_warning_report] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")



@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_warning_analyze3():
    assert os.path.exists(JPG_PATH), f"测试文件不存在: {JPG_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(JPG_PATH, "rb") as f:
            files = {"file": (JPG_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_003"}
            r = await c.post("/warning/analyze", files=files, data=data)
    assert r.status_code == 200
    print(f"[warning_analyze] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")



@pytest.mark.asyncio
@pytest.mark.order(8)
async def test_save_warning_report3():
    assert os.path.exists(JPG_PATH), f"测试文件不存在: {JPG_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(JPG_PATH, "rb") as f:
            files = {"file": (JPG_NAME, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"warning_number": "warning_003"}
            r = await c.post("/warning/save_warning_report", files=files, data=data)
    assert r.status_code == 200
    print(f"[save_warning_report] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(9)
async def test_delete_warning_report3():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/warning/delete_warning_report", json="warning_003")
    assert r.status_code == 200
    print(f"[delete_warning_report] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")




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
    content_type = r.headers.get("content-type", "")
    if "application/json" in content_type:
        resp = r.json()
        print(f"[generate_notice_doc] 响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    else:
        # 返回的是文件流（docx），保存到本地验证
        save_path = os.path.join(os.path.dirname(__file__), "test_notice_output.docx")
        with open(save_path, "wb") as f:
            f.write(r.content)
        print(f"[generate_notice_doc] 响应为文件，已保存到: {save_path}，大小: {len(r.content)} bytes")
