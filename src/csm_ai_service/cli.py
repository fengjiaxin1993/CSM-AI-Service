import shutil
import subprocess
import sys
import warnings
from pathlib import Path

# 屏蔽 pydantic 模块下所有 UserWarning
warnings.filterwarnings("ignore", category=UserWarning, module=r"pydantic.*")
# 屏蔽 langgraph 的 LangChainPendingDeprecationWarning
warnings.filterwarnings("ignore", message=".*allowed_objects.*", category=Warning)
import click
from csm_ai_service.utils import build_logger
from csm_ai_service.startup import main as startup_main
from csm_ai_service.init_database import main as kb_main, create_tables
from csm_ai_service.settings import Settings

logger = build_logger()


# 步骤1：创建命令组（所有子命令的容器）
@click.group(help="chatchat 命令行工具")
def main():
    ...


# 步骤2：添加子命令1：init（初始化配置）
@main.command("init", help="项目初始化")
def init():
    Settings.set_auto_reload(False)
    bs = Settings.basic_settings
    logger.info(f"开始初始化项目数据目录：{Settings.CHATCHAT_ROOT}")
    Settings.basic_settings.make_dirs()
    logger.success("创建所有数据目录：成功。")
    if (bs.PACKAGE_ROOT / "data/knowledge_base/samples" != Path(bs.KB_ROOT_PATH) / "samples"):
        shutil.copytree(bs.PACKAGE_ROOT / "data/knowledge_base/samples/content", Path(bs.KB_ROOT_PATH) / "samples/content",
                        dirs_exist_ok=True)
        shutil.copytree(bs.PACKAGE_ROOT / "data/nltk_data",
                        Path(bs.DATA_PATH) / "nltk_data",
                        dirs_exist_ok=True)
        shutil.copytree(bs.PACKAGE_ROOT / "data/template_file",
                        Path(bs.DATA_PATH) / "template_file",
                        dirs_exist_ok=True)
        shutil.copytree(bs.PACKAGE_ROOT / "data/frontend",
                        Path(bs.DATA_PATH) / "frontend",
                        dirs_exist_ok=True)
    if bs.PACKAGE_ROOT / "test_api" != bs.TEST_API_PATH:
        shutil.copytree(bs.PACKAGE_ROOT / "test_api",
                        bs.TEST_API_PATH,
                        dirs_exist_ok=True)
    logger.success("复制 samples 知识库文件：成功。")
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
