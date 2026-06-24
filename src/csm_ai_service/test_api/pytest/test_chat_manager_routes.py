"""测试 /chat_manager 接口"""
import json
import httpx
import pytest

import yaml

# 从 YAML 配置文件读取测试服务地址
_config_path = "test_config.yaml"
with open(_config_path, "r", encoding="utf-8") as f:
    _config = yaml.safe_load(f)

BASE = _config["server"]["base_url"]
TIMEOUT = _config["server"].get("timeout", 120)


@pytest.mark.asyncio
async def test_possible_questions():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat_manager/possible_questions", json="4")
    assert r.status_code == 200
    print(f"[possible_questions] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


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
async def test_save_conversation():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat_manager/conversation/save_conversation", json={
            "conversation_id": "c1", "user_id": "u1"
        })
    assert r.status_code == 200
    print(f"[save_conversation] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_get_conversations():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat_manager/conversations", json={
            "user_id": "u1", "limit": 5, "offset": 0
        })
    assert r.status_code == 200
    print(f"[get_conversations] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_get_conversation_messages():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat_manager/conversation/messages", json={
            "conversation_id": "c1", "offset": 0, "limit": 10
        })
    assert r.status_code == 200
    print(f"[get_conversation_messages] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_toggle_favorite():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat_manager/conversation/toggle_favorite", json={
            "conversation_id": "c1", "is_favorite": 1
        })
    assert r.status_code == 200
    print(f"[toggle_favorite] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_delete_conversation():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/chat_manager/conversation/delete", json="c1")
    assert r.status_code == 200
    print(f"[delete_conversation] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
