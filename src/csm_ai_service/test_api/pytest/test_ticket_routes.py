"""测试 /ticket 接口"""
import json
import httpx
import pytest

from test_api.pytest.config import BASE


@pytest.mark.asyncio
async def test_associate_device():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/ticket/associate_device", json={
            "maintenance_object": "叶家河光储正向隔离装置",
            "affected_object": "叶家河光储正向隔离装置",
            "work_content": "重新配置策略",
            "is_substation": True
        })
    assert r.status_code == 200
    assert r.json()["code"] == 200
    print(f"[associate_device] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
async def test_associate_device_not_substation():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/ticket/associate_device", json={
            "maintenance_object": "加密装置",
            "affected_object": "加密装置",
            "work_content": "检查策略",
            "is_substation": False
        })
    assert r.status_code == 200
    print(f"[associate_device_not_substation] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
