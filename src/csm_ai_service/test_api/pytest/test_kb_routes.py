"""测试 /knowledge_base 接口"""
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
PDF_NAME = "《电力监控系统安全防护规定》27号令.pdf"
PDF_PATH = os.path.join(os.path.dirname(__file__), "data", PDF_NAME)



@pytest.mark.asyncio
async def test_list_kbs():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.get("/knowledge_base/list_knowledge_bases")
    assert r.status_code == 200
    assert r.json()["code"] == 200
    print(f"[list_kbs] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_list_files():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.get("/knowledge_base/list_files", params={"knowledge_base_name": "samples"})
    assert r.status_code == 200
    print(f"[list_files] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_create_kb():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post("/knowledge_base/create_knowledge_base", json={
            "knowledge_base_name": "test_pytest_kb",
            "vector_store_type": "faiss",
            "kb_info": "pytest test kb"
        })
    assert r.status_code == 200
    print(f"[create_kb] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")



@pytest.mark.asyncio
async def test_upload_docs():
    assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        with open(PDF_PATH, "rb") as f:
            files = {"files": (PDF_NAME, f, "application/pdf")}
            data = {"knowledge_base_name": "test_pytest_kb", "override": True, "to_vector_store": True}
            r = await c.post("/knowledge_base/upload_docs", files=files, data=data)
    assert r.status_code == 200
    print(f"[upload_docs] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_search_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post("/knowledge_base/search_docs", json={
            "query": "电力监控系统如何分区？", "knowledge_base_name": "test_pytest_kb",
            "top_k": 3, "score_threshold": 0.2
        })
    assert r.status_code == 200
    print(f"[search_docs] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")



@pytest.mark.asyncio
async def test_delete_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post("/knowledge_base/delete_docs", json={
            "knowledge_base_name": "test_pytest_kb",
            "file_names": [PDF_NAME],
            "delete_content": True,
            "not_refresh_vs_cache": False
        })
    assert r.status_code == 200
    print(f"[delete_docs] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")




@pytest.mark.asyncio
async def test_delete_kb():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post("/knowledge_base/delete_knowledge_base", json=
            "test_pytest_kb"
        )
    assert r.status_code == 200
    print(f"[delete_kb] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")



@pytest.mark.asyncio
async def test_search_temp_docs():
    """上传临时文档 → 获取 file_id → 用 file_id 作为 knowledge_id 搜索"""
    assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        # 1. 上传临时文档
        with open(PDF_PATH, "rb") as f:
            files = {"files": (PDF_NAME, f, "application/pdf")}
            upload_r = await c.post("/knowledge_base/upload_temp_docs", files=files)
        assert upload_r.status_code == 200
        upload_data = upload_r.json()
        print(f"[upload_temp_docs] 响应: {json.dumps(upload_data, ensure_ascii=False, indent=2)}")
        file_id = upload_data.get("data", {}).get("file_id", "")
        assert file_id, f"上传失败，未获取到 file_id，响应: {upload_data}"

        # 2. 用 file_id 搜索临时文档（参数为 query 参数，非 JSON body）
        r = await c.post("/knowledge_base/search_temp_docs", params={
            "knowledge_id": file_id, "query": "电力监控系统如何分区？", "top_k": 3, "score_threshold": 0.2
        })
    assert r.status_code == 200
    print(f"[search_temp_docs] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")