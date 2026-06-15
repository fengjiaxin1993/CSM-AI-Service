from typing import Optional

import httpx

# curl -X 'POST' \
#   'http://127.0.0.1:7861/tools/alert/overview' \
#   -H 'accept: application/json' \
#   -H 'Content-Type: application/json' \
#   -d '{
#   "start_date": "2024-01-01",
#   "end_date": "2024-01-07"
# }'
def call_api(name: str, method: str, headers: dict, timeout: int, payload: dict) -> Optional[str]:
    """同步调用API"""
    base_url = "http://127.0.0.1:7861"
    url_path = "tools/alert/overview"

    # 正确处理 URL 拼接
    full_url = f"{base_url}/{url_path}"

    print(f"API请求: {method.upper()} {full_url}, payload={payload}")

    try:
        method = method.upper()
        with httpx.Client(timeout=timeout) as client:
            if method == "GET":
                resp = client.get(full_url, params=payload, headers=headers)
            else:
                resp = client.post(full_url, json=payload, headers=headers)
        resp.raise_for_status()
        print(f"API响应: {resp.status_code}")
        return resp.text
    except httpx.TimeoutException as e:
        print(f"API调用超时: {name}, timeout={timeout}s, error={e}")
        return None
    except httpx.ConnectError as e:
        print(f"API连接失败: {name}, url={full_url}, error={e}")
        return None
    except Exception as e:
        print(f"API调用失败: {name}, error={type(e).__name__}: {e}")
        return None

if __name__ == "__main__":
    res = call_api("overview", "POST", {}, 30, {"start_date": "2025-06-01", "end_date": "2025-06-02"})
    print(res)

