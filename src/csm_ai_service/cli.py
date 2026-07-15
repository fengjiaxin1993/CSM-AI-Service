import shutil
import sys
import warnings
from pathlib import Path

# 屏蔽 pydantic 模块下所有 UserWarning
warnings.filterwarnings("ignore", category=UserWarning, module=r"pydantic.*")
# 屏蔽 langgraph 的 LangChainPendingDeprecationWarning
warnings.filterwarnings("ignore", message=".*allowed_objects.*", category=Warning)
import click
from csm_ai_service.utils import build_logger
from csm_ai_service.settings import Settings

logger = build_logger()


# 步骤1：创建命令组（所有子命令的容器）
@click.group(help="chatchat 命令行工具")
def main():
    ...


# 步骤2：添加子命令1：init（初始化配置）
@main.command("init", help="项目初始化")
def init():
    # 延迟导入，避免 Windows spawn 模式下死锁
    from csm_ai_service.init_database import create_tables

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


# 步骤3：添加子命令2：start（启动服务）— 使用 Click 的 lazy group 实现真正的延迟导入
# 关键：不能让 startup 和 init_database 在模块顶层被导入，因为它们的导入链包含：
#   - server/db/base.py: engine = create_engine(...)  导入时创建数据库引擎
#   - audit_graph.py: llm = get_ChatOpenAI(...)       导入时创建 LLM 实例
#   - audit_graph.py: GLOBAL_AUDIT_GRAPH = create_graph()  导入时编译 LangGraph
#   - server/utils.py: import multiprocessing          Windows spawn 模式风险
# 这些在模块导入时执行会导致卡住或极慢。


@main.command("start", help="启动服务",
              context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def start(args):
    """启动 API 服务 — 仅在命令执行时才导入重型依赖"""
    from csm_ai_service.startup import run_api_server
    run_api_server()


@main.command("kb", help="知识库相关功能",
              context_settings=dict(ignore_unknown_options=True))
@click.option(
    "-r", "--recreate-vs", is_flag=True,
    help="recreate vector store.",
)
@click.option(
    "--create-tables", is_flag=True,
    help="create empty tables if not existed",
)
@click.option(
    "--clear-tables", is_flag=True,
    help="create empty tables, or drop the database tables before recreate vector stores",
)
def kb(recreate_vs, create_tables, clear_tables):
    """知识库管理 — 仅在命令执行时才导入重型依赖"""
    from csm_ai_service.init_database import main as kb_main_func
    # 直接调用 worker 函数，避免 multiprocessing.Process 在 Windows 上的 spawn 问题
    kb_main_func.callback(recreate_vs=recreate_vs, create_tables=create_tables, clear_tables=clear_tables)


# 项目入口（调用命令组）
if __name__ == "__main__":
    main()
