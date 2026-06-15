# 构建和安装指南

## 1. 清理旧构建

```bash
# 删除旧构建文件
rm -rf dist/ 

# 卸载旧版本
pip uninstall icdo -y
```

## 2. 重新构建

```bash
# 使用 poetry 构建
poetry build
```

## 3. 安装

```bash
# 安装 wheel 包
pip install dist/icdo-1.0.0-py3-none-any.whl
```

## 4. 运行

```bash
# 在任意目录初始化
mkdir /tmp/test_icdo
cd /tmp/test_icdo
mkdir data
将 init_data下的目录 拷贝到 当前data目录下


icdo init # 初始化 会生成一些yaml文件和data目录下的文件夹补充
icdo kb -r # 填充知识库
icdo start # 启动服务
```

