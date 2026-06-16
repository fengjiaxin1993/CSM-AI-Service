import os

import pytest

# 集中配置服务地址
BASE = "http://192.168.88.120:7861"


@pytest.fixture(scope="session")
def base_url():
    """返回测试服务的基础 URL"""
    return BASE
