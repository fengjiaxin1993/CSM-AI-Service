"""测试 /ticket 接口"""
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
async def test_associate_device():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
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
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post("/ticket/associate_device", json={
            "maintenance_object": "加密装置",
            "affected_object": "加密装置",
            "work_content": "检查策略",
            "is_substation": False
        })
    assert r.status_code == 200
    print(f"[associate_device_not_substation] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
