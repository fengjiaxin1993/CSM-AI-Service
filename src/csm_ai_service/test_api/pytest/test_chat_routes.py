"""测试 /chat 接口"""
import json
import os

import httpx
import pytest

BASE = "http://127.0.0.1:7861"
PDF_NAME = "《电力监控系统安全防护规定》27号令.pdf"
PDF_PATH = os.path.join(os.path.dirname(__file__), "data", PDF_NAME)

@pytest.mark.asyncio
async def test_chat():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/chat", json={"query": "你好", "stream": False})
    assert r.status_code == 200
    print(f"[chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_chat_stream():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/chat", json={"query": "你好", "stream": True})
    assert r.status_code == 200
    print(f"[chat_stream] 响应(前500字符): {r.text[:500]}")


@pytest.mark.asyncio
async def test_mem_chat():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/mem_chat", json={
            "query": "你好", "conversation_id": "test", "history_len": 3, "stream": False
        })
    assert r.status_code == 200
    print(f"[mem_chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_similar_mem_chat():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/similar_mem_chat", json={
            "query": "你好", "user_id": "test_user", "stream": False
        })
    assert r.status_code == 200
    print(f"[similar_mem_chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_kb_chat():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/kb_chat", json={
            "query": "电力监控系统如何分区？", "kb_name": "samples", "stream": False, "return_direct": False
        })
    assert r.status_code == 200
    print(f"[kb_chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_agent_chat1():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/chat_agent", json={
            "query": "电力监控系统如何分区？", "stream": False, "conversation_id": "test_agent"
        })
    assert r.status_code == 200
    print(f"[agent_chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_agent_chat2():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/chat_agent", json={
            "query": "地球距离太阳多远？", "stream": False, "conversation_id": "test_agent"
        })
    assert r.status_code == 200
    print(f"[agent_chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_agent_chat3():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/chat_agent", json={
            "query": "最近7天告警情况如何", "stream": False, "conversation_id": "test_agent"
        })
    assert r.status_code == 200
    print(f"[agent_chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_unified_chat():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat/unified_chat", json={
            "query": "地球距离太阳多远", "stream": False,
            "conversation_id": "c1", "file_id": ""
        })
    assert r.status_code == 200
    print(f"[unified_chat] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_unified_chat_with_file():
    import os
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        # 上传当前目录下的真实 PDF 文件
        assert os.path.exists(PDF_PATH), f"测试文件不存在: {PDF_PATH}"
        with open(PDF_PATH, "rb") as f:
            upload_r = await c.post(
                "/knowledge_base/upload_temp_docs",
                files={"files": ("《电力监控系统安全防护规定》27号令.pdf", f, "application/pdf")},
                data={"chunk_size": 500, "chunk_overlap": 50, "zh_title_enhance": True},
            )
        assert upload_r.status_code == 200
        upload_data = upload_r.json()
        print(f"[upload_temp_docs] 响应: {json.dumps(upload_data, ensure_ascii=False, indent=2)}")
        file_id = upload_data.get("data", {}).get("file_id", "")
        assert file_id, f"上传失败，未获取到 file_id，响应: {upload_data}"

        # 用 file_id 进行文件对话
        r = await c.post("/chat/unified_chat", json={
            "query": "电力监控系统如何分区？", "stream": False,
            "conversation_id": "c1", "file_id": file_id
        })
    assert r.status_code == 200
    print(f"[unified_chat_with_file] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
