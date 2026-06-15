"""测试 /parse_pdf 接口"""
import os

import httpx
import pytest

BASE = "http://127.0.0.1:7861"
PDF_NAME = "2018泉州供电公司调度自动化系统信息安全等级测评报告-S2A3G3.pdf"
PDF_PATH = os.path.join(os.path.dirname(__file__), PDF_NAME)


@pytest.mark.asyncio
async def test_extract_safe_table():
    assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(PDF_PATH, "rb") as f:
            files = {"file": (PDF_NAME, f, "application/pdf")}
            r = await c.post("/parse_pdf/extract_safe_table", files=files)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_extract_dbcp_info():
    assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(PDF_PATH, "rb") as f:
            files = {"file": (PDF_NAME, f, "application/pdf")}
            r = await c.post("/parse_pdf/extract_dbcp_info", files=files)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_extract_safe_split_table():
    assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        with open(PDF_PATH, "rb") as f:
            files = {"file": (PDF_NAME, f, "application/pdf")}
            r = await c.post("/parse_pdf/extract_safe_split_table", files=files)
    assert r.status_code == 200
