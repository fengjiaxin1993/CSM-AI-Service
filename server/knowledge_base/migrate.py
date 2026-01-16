import os
from datetime import datetime
from typing import List, Literal
from dateutil.parser import parse
from settings import Settings
from server.db.base import Base, engine

from server.db.session import session_scope
from server.knowledge_base.kb_service.base import (
    KBServiceFactory,
    SupportedVSType,
)
from server.knowledge_base.utils import (
    KnowledgeFile,
    files2docs_in_thread,
    get_file_path,
    list_files_from_folder,
    list_kbs_from_folder,
)
from utils import build_logger
from server.utils import get_default_embedding

logger = build_logger()


def create_tables():
    Base.metadata.create_all(bind=engine)


def reset_tables():
    Base.metadata.drop_all(bind=engine)
    create_tables()


def file_to_kbfile(kb_name: str, files: List[str]) -> List[KnowledgeFile]:
    kb_files = []
    for file in files:
        try:
            kb_file = KnowledgeFile(filename=file, knowledge_base_name=kb_name)
            kb_files.append(kb_file)
        except Exception as e:
            msg = f"{e}，已跳过"
            logger.error(f"{e.__class__.__name__}: {msg}")
    return kb_files


def folder2db(
        kb_names: List[str],
        mode: Literal["recreate_vs", "update_in_db", "increment"],
        vs_type: Literal["chromadb"] = Settings.kb_settings.DEFAULT_VS_TYPE,
        embed_model: str = get_default_embedding(),
        chunk_size: int = Settings.kb_settings.CHUNK_SIZE,
        chunk_overlap: int = Settings.kb_settings.OVERLAP_SIZE,
        zh_title_enhance: bool = Settings.kb_settings.ZH_TITLE_ENHANCE,
):
    """
    use existed files in local folder to populate database and/or vector store.
    set parameter `mode` to:
        recreate_vs: recreate all vector store and fill info to database using existed files in local folder
        update_in_db: update vector store and database info using local files that existed in database only
        increment: create vector store and database info for local files that not existed in database only
    """

    def files2vs(kb_name: str, kb_files: List[KnowledgeFile]) -> List:
        result = []
        for success, res in files2docs_in_thread(
                kb_files,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                zh_title_enhance=zh_title_enhance,
        ):
            if success:
                _, filename, docs = res
                # print(
                #     f"正在将 {kb_name}/{filename} 添加到向量库，共包含{len(docs)}条文档"
                # )
                kb_file = KnowledgeFile(filename=filename, knowledge_base_name=kb_name)
                kb_file.splited_docs = docs
                kb.add_doc(kb_file=kb_file, not_refresh_vs_cache=True)
                result.append({"kb_name": kb_name, "file": filename, "docs": docs})
            else:
                print(res)
        return result

    kb_names = kb_names or list_kbs_from_folder()
    for kb_name in kb_names:
        start = datetime.now()
        kb = KBServiceFactory.get_service(kb_name, vs_type, embed_model)
        if not kb.exists():
            kb.create_kb()

        # 清除向量库，从本地文件重建
        if mode == "recreate_vs":
            kb.clear_vs()
            kb.create_kb()
            kb_files = file_to_kbfile(kb_name, list_files_from_folder(kb_name))
            result = files2vs(kb_name, kb_files)
            kb.save_vector_store()
        elif mode == "update_in_db":
            files = kb.list_files()
            kb_files = file_to_kbfile(kb_name, files)
            result = files2vs(kb_name, kb_files)
            kb.save_vector_store()
        # 对比本地目录与数据库中的文件列表，进行增量向量化
        elif mode == "increment":
            db_files = kb.list_files()
            folder_files = list_files_from_folder(kb_name)
            files = list(set(folder_files) - set(db_files))
            kb_files = file_to_kbfile(kb_name, files)
            result = files2vs(kb_name, kb_files)
            kb.save_vector_store()
        else:
            print(f"unsupported migrate mode: {mode}")
        end = datetime.now()
        kb_path = (
            f"知识库路径\t：{kb.kb_path}\n"
            if kb.vs_type() == SupportedVSType.FAISS
            else ""
        )
        file_count = len(kb_files)
        success_count = len(result)
        docs_count = sum([len(x["docs"]) for x in result])
        print("\n" + "-" * 100)
        print(
            (
                f"知识库名称\t：{kb_name}\n"
                f"知识库类型\t：{kb.vs_type()}\n"
                f"向量模型：\t：{kb.embed_model}\n"
            )
            + kb_path
            + (
                f"文件总数量\t：{file_count}\n"
                f"入库文件数\t：{success_count}\n"
                f"知识条目数\t：{docs_count}\n"
                f"用时\t\t：{end - start}"
            )
        )
        print("-" * 100 + "\n")
        return result


def prune_db_docs(kb_names: List[str]):
    """
    删除 文件在数据库中存在，但是在本地文件夹不存在的文件
    delete docs in database that not existed in local folder.
    it is used to delete database docs after user deleted some doc files in file browser
    """
    for kb_name in kb_names:
        kb = KBServiceFactory.get_service_by_name(kb_name)
        if kb is not None:
            files_in_db = kb.list_files()
            files_in_folder = list_files_from_folder(kb_name)
            files = list(set(files_in_db) - set(files_in_folder))
            kb_files = file_to_kbfile(kb_name, files)
            for kb_file in kb_files:
                kb.delete_doc(kb_file, not_refresh_vs_cache=True)
                print(f"success to delete docs for file: {kb_name}/{kb_file.filename}")
            kb.save_vector_store()


def prune_folder_files(kb_names: List[str]):
    """
    删除 文件在本地文件夹， 但是不在数据库中的文件
    delete doc files in local folder that not existed in database.
    it is used to free local disk space by delete unused doc files.
    """
    for kb_name in kb_names:
        kb = KBServiceFactory.get_service_by_name(kb_name)
        if kb is not None:
            files_in_db = kb.list_files()
            files_in_folder = list_files_from_folder(kb_name)
            files = list(set(files_in_folder) - set(files_in_db))
            for file in files:
                os.remove(get_file_path(kb_name, file))
                print(f"success to delete file: {kb_name}/{file}")
