# CSM-AI-Service
langchain-chatchat大模型服务项目，要部署在凝思/麒麟系统，这两个国产系统配置较低，
因此需要适配环境，通过conda适配，可以解决依赖的GCC版本过低的问题


## 项目解决方案
# pip vs conda
## pip 需要下载源码并在系统编译， conda直接下载编译好的二进制编码，不依赖操作系统
## 因此使用conda ,可以在凝思系统/麒麟系统上 运行代码，并可后续打包成二进制文件进行部署启动。


## 1. 环境安装, 在凝思系统/麒麟系统上 安装好anaconda/miniconda

- conda chatchat create -f conda-environment.yaml

## 2. 项目启动说明
- python cli.py init # 生成配置文件yaml
- python cli.py kb -r # 根据data中的samples中的文件，构建向量进行插入
- python cli.py start # 启动api服务


## 3. 打包成二进制文件，进行启动
- python setup.py build
- 进入到 build文件夹中，找到 chatchat 二进制文件
- chatchat init
- chatchat kb -r # 根据data中的samples中的文件，构建向量进行插入
- chatchat start # 启动api服务