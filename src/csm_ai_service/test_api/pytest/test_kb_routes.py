"""测试 /knowledge_base 接口"""
import io
import httpx
import pytest

BASE = "http://127.0.0.1:7861"


@pytest.mark.asyncio
async def test_list_kbs():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/knowledge_base/list_knowledge_bases")
    assert r.status_code == 200
    assert r.json()["code"] == 200


@pytest.mark.asyncio
async def test_create_kb():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/create_knowledge_base", json={
            "knowledge_base_name": "test_pytest_kb",
            "vector_store_type": "faiss",
            "kb_info": "pytest test kb"
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_files():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.get("/knowledge_base/list_files", params={"knowledge_base_name": "samples"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/search_docs", json={
            "query": "测试", "knowledge_base_name": "samples",
            "top_k": 3, "score_threshold": -1.0
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_upload_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        content = b"test document content"
        files = {"files": ("test.txt", io.BytesIO(content), "text/plain")}
        data = {"knowledge_base_name": "samples", "override": True, "to_vector_store": False}
        r = await c.post("/knowledge_base/upload_docs", files=files, data=data)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/delete_docs", json={
            "knowledge_base_name": "samples",
            "file_names": ["test.txt"],
            "delete_content": True,
            "not_refresh_vs_cache": True
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_info():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/update_info", json={
            "knowledge_base_name": "samples",
            "kb_info": "pytest updated info"
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/update_docs", json={
            "knowledge_base_name": "samples",
            "file_names": ["test.txt"],
            "not_refresh_vs_cache": True
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_recreate_vector_store():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/recreate_vector_store", json={
            "knowledge_base_name": "samples",
            "allow_empty_kb": True,
            "not_refresh_vs_cache": True
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_upload_temp_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        content = b"temp test"
        files = {"files": ("temp.txt", io.BytesIO(content), "text/plain")}
        r = await c.post("/knowledge_base/upload_temp_docs", files=files)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_temp_docs():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/search_temp_docs", json={
            "knowledge_id": "", "query": "test", "top_k": 3, "score_threshold": -1.0
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_kb():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/knowledge_base/delete_knowledge_base", json={
            "knowledge_base_name": "test_pytest_kb"
        })
    assert r.status_code == 200
