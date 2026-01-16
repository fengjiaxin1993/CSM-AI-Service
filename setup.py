#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
@author: feng jiaxin
@file: setup.py
@time 2026/01/13 16:12
@desc
"""
import sys
from pathlib import Path
import os
from cx_Freeze import setup, Executable


# 1. 提升Python递归深度限制
sys.setrecursionlimit(5000)
# 2. 禁用cx_Freeze的自动依赖扫描（避免递归扫描出错）
os.environ["CX_FREEZE_SKIP_DEPENDENCY_SCAN"] = "1"

base = None
if sys.platform == "win32":
    base = None
# 定义要打包的 data 目录（项目根目录下的 data）
project_root = Path(__file__).parent
data_dir = project_root / "data"
include_files = []
if data_dir.exists():
    # 配置：将项目的 data 目录，打包到二进制程序同级的 "data" 目录下（源目录）
    include_files.append((str(data_dir), "data"))

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    'packages': ['server','fastapi','uvicorn','openai','starlette','argparse','langchain','sqlalchemy',
                 'langchain_community','langchain_core', 'tenacity','pydantic','memoization','ruamel','asyncio'],  # 依赖的包，python自己无法找到的包
    'excludes': [],  # 不包含那些包
    "include_files": include_files
}

executables = [
    Executable(
        script="cli.py",
        base=base,
        target_name="chatchat" if sys.platform != "win32" else "chatchat.exe"
    )
]

setup(
    name='chatchat',
    version='1.0',
    description='csm 问答助手服务',
    executables=executables,
    options={'build_exe': build_exe_options},
)
