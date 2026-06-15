"""测试 /warning_handle 接口"""
import json
import httpx
import pytest

BASE = "http://127.0.0.1:7861"


@pytest.mark.asyncio
async def test_platform_warning():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        r = await c.post("/warning_handle/warning", json={
            "IP": "40.101.37.2",
            "destinationIp": "未知设备",
            "alertLevel": "紧急",
            "deviceType": "7",
            "logType": "2",
            "logSubType": "7",
            "alertStartTime": "2025/12/10 13:32",
            "currentAlertTime": "2025/12/10 13:32",
            "alertCount": "10",
            "alertStatusFlag": "0",
            "alertDescription": "端口扫描",
            "eventType": "0",
            "assetName": "未知设备",
            "assetId": "",
            "assetSubType": "服务器",
            "assetRegion": "01119901030000004",
            "alertType": "105",
            "alertSubType": "22",
            "newAlertCode": "SVR105022",
            "reportingDeviceType": "6",
            "regionName": "0021990103",
            "alertUniqueId": "344632032224759600",
            "regulationCloudId": "01119901030000004",
            "alertSource": "1001",
            "reportingDevice": "华中网调_二次安全防护系统",
            "wmac": "9256668770066516552"
        })
    assert r.status_code == 200
    assert r.json()["code"] == "0"
    print(f"[platform_warning] 响应: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
