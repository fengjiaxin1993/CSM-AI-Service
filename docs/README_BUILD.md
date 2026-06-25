# 构建和离线安装指南

## 方式一：自动构建离线安装包（推荐）

### Windows

```bash
build_offline.bat
```

### Linux / Mac

```bash
chmod +x build_offline.sh
./build_offline.sh
```

构建完成后，`dist/` 目录包含：
- `icdo-1.2.2-py3-none-any.whl` — 项目 wheel 包
- `offline_packages/` — 所有依赖的 wheel 包
- `requirements_offline.txt` — 依赖列表

### 离线安装

将整个 `dist/` 目录拷贝到目标机器，然后执行：

```bash
pip install --no-index --find-links=dist/offline_packages dist/icdo-1.2.2-py3-none-any.whl
```

初始化并启动：

```bash
mkdir /tmp/test_icdo && cd /tmp/test_icdo
icdo init
icdo kb -r   # 填充知识库（可选）
icdo start   # 启动服务
```

---

## 方式二：手动构建

### 1. 清理旧构建

```bash
rm -rf dist/
pip uninstall icdo -y
```

### 2. 构建 wheel

```bash
poetry build
```

> 产出：`dist/icdo-1.2.2-py3-none-any.whl`

### 3. 在线安装（需网络）

```bash
pip install dist/icdo-1.2.2-py3-none-any.whl
```

### 4. 导出并下载依赖（用于离线安装）

```bash
# 导出依赖列表
poetry export -f requirements.txt --without-hashes --only main -o dist/requirements_offline.txt

# 下载所有依赖 wheel
pip download -r dist/requirements_offline.txt -d dist/offline_packages --prefer-binary
```

### 5. 离线安装

```bash
pip install --no-index --find-links=dist/offline_packages dist/icdo-1.2.2-py3-none-any.whl
```

---

## 常见问题

### poetry-plugin-export 未安装

如果 `poetry export` 命令报错，需要安装导出插件：

```bash
poetry self add poetry-plugin-export
```

### 首次运行必须先初始化

```bash
icdo init   # 生成配置文件和目录结构
icdo start  # 启动服务
```

如果未先执行 `icdo init`，`icdo start` 会因缺少配置文件而阻塞或报错。
