"""测试 /api/rules 接口"""
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

# 用于测试的规则数据，按顺序创建->查询->更新->删除
_test_rule_id = None


@pytest.mark.asyncio
@pytest.mark.order(1)
async def test_init_default_rules():
    """导入默认规则"""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post("/api/rules/init_default")
    assert r.status_code == 200
    print(f"[init_default_rules] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(2)
async def test_list_rules():
    """获取规则列表"""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.get("/api/rules/list")
    assert r.status_code == 200
    print(f"[list_rules] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(3)
async def test_create_rule():
    """创建新规则"""
    global _test_rule_id
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post("/api/rules/create", json={
            "name": "测试规则_自动",
            "description": "自动化测试创建的规则",
            "chapter_keywords": ["测试", "自动化"],
            "judge_logic": "包含关键词则通过",
        })
    assert r.status_code == 200
    resp = r.json()
    print(f"[create_rule] 响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    if resp.get("success"):
        _test_rule_id = resp.get("data", {}).get("id")


@pytest.mark.asyncio
@pytest.mark.order(4)
async def test_get_rule_detail():
    """获取规则详情"""
    global _test_rule_id
    if not _test_rule_id:
        pytest.skip("前置创建规则失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.get(f"/api/rules/detail/{_test_rule_id}")
    assert r.status_code == 200
    print(f"[get_rule_detail] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(5)
async def test_update_rule():
    """更新规则"""
    global _test_rule_id
    if not _test_rule_id:
        pytest.skip("前置创建规则失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post(f"/api/rules/update/{_test_rule_id}", json={
            "name": "测试规则_已更新",
            "description": "更新后的规则描述",
            "chapter_keywords": ["更新", "测试"],
            "judge_logic": "更新后的判断逻辑",
        })
    assert r.status_code == 200
    print(f"[update_rule] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(6)
async def test_delete_rule():
    """删除规则"""
    global _test_rule_id
    if not _test_rule_id:
        pytest.skip("前置创建规则失败，跳过")
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.post(f"/api/rules/delete/{_test_rule_id}")
    assert r.status_code == 200
    print(f"[delete_rule] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")


@pytest.mark.asyncio
@pytest.mark.order(7)
async def test_get_rule_detail_not_found():
    """查询不存在的规则"""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:
        r = await c.get("/api/rules/detail/99999")
    assert r.status_code == 200
    print(f"[get_rule_detail_not_found] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
