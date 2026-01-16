# Description: 初始化数据库，包括创建表、导入数据、更新向量空间等操作
from datetime import datetime
import multiprocessing as mp
import sys
import time

import click

from settings import Settings
from server.knowledge_base.migrate import (
    create_tables,
    reset_tables, folder2db,
)
from utils import build_logger
from server.utils import get_default_embedding

import nltk

Settings.set_auto_reload(False)
bs = Settings.basic_settings
nltk.data.path.append(bs.NLTK_DATA_PATH)
logger = build_logger()


def worker(args: dict):
    start_time = datetime.now()

    try:
        if args.get("create_tables"):
            create_tables()  # confirm tables exist

        if args.get("clear_tables"):
            reset_tables()
            print("database tables reset")

        if args.get("recreate_vs"):
            create_tables()
            print("recreating all vector stores")
            folder2db(
                kb_names=args.get("kb_name"), mode="recreate_vs")
        end_time = datetime.now()
        print(f"总计用时\t：{end_time - start_time}\n")
    except Exception as e:
        logger.error(e, exc_info=True)


@click.command(help="知识库相关功能")
@click.option(
    "-r",
    "--recreate-vs",
    is_flag=True,
    help=(
            """
            recreate vector store.
            use this option if you have copied document files to the content folder, but vector store has not been populated or DEFAUL_VS_TYPE/DEFAULT_EMBEDDING_MODEL changed.
            """
    ),
)
@click.option(
    "--create-tables",
    is_flag=True,
    help=("create empty tables if not existed"),
)
@click.option(
    "--clear-tables",
    is_flag=True,
    help=(
            "create empty tables, or drop the database tables before recreate vector stores"
    ),
)
def main(**kwds):
    p = mp.Process(target=worker, args=(kwds,), daemon=True)
    p.start()
    while p.is_alive():
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            logger.warning("Caught KeyboardInterrupt! Setting stop event...")
            p.terminate()
            sys.exit()


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
