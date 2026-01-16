# cli_group.py
import os
import shutil
import sys
from pathlib import Path
import click
from utils import build_logger
from startup import main as startup_main
from init_database import main as kb_main, create_tables
from settings import Settings

logger = build_logger()


# ========== 新增：路径适配 + 文件夹复制工具函数 ==========
def get_real_path(relative_path: str) -> Path:
    """适配开发环境/打包后环境，获取文件/目录的真实路径"""
    if getattr(sys, 'frozen', False):
        binary_dir = Path(sys.executable).parent
        real_path = binary_dir / relative_path
    else:
        current_script_dir = Path(__file__).parent
        real_path = current_script_dir / relative_path
    return real_path.resolve()


def copy_data_to_binary_dir(overwrite: bool = False) -> None:
    """将 data 文件夹复制到二进制程序所在目录"""
    data_src = get_real_path("data")
    data_dst = Path(sys.executable).parent / "data"  # 目标目录：二进制同级的 data 目录（与源同名）

    if not data_src.exists():
        raise FileNotFoundError(f"源 data 目录不存在：{data_src}，请检查打包配置")

    if data_dst.exists():
        if not overwrite:
            click.echo(f"✅ 目标 data 目录已存在，跳过复制：{data_dst}")
            return
        else:
            click.echo(f"🔄 目标 data 目录已存在，删除后重新复制")
            shutil.rmtree(data_dst)

    shutil.copytree(data_src, data_dst, dirs_exist_ok=False)
    click.echo(f"✅ data 目录复制完成：{data_dst}")


# 步骤1：创建命令组（所有子命令的容器）
@click.group(help="chatchat 命令行工具")
def main():
    ...


# 步骤2：添加子命令1：init（初始化配置）
@main.command("init", help="项目初始化")
def init():
    Settings.set_auto_reload(False)
    logger.info(f"开始初始化项目数据目录：{Settings.CHATCHAT_ROOT}")
    Settings.basic_settings.make_dirs()
    logger.info("创建所有数据目录：成功。")
    logger.info("开始创建相关表信息")
    create_tables()
    logger.info("创建表信息：成功。")
    Settings.create_all_templates()
    Settings.set_auto_reload(True)

    logger.info("生成默认配置文件：成功。")
    logger.warning("<red>请先检查 model_settings.yaml 里模型平台、LLM模型和Embed模型信息正确</red>")


main.add_command(startup_main, "start")
main.add_command(kb_main, "kb")

# 项目入口（调用命令组）
if __name__ == "__main__":
    main()
