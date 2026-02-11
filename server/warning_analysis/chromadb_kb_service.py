import threading
import time
import uuid
from typing import List
import chromadb
from chromadb.types import Collection

from server.utils import get_Embeddings, get_default_embedding

from settings import Settings

# 知识库插入、搜索
from server.utils import build_logger
logger = build_logger()

# 🌟 核心1：项目启动时初始化【全局单例】ChromaDB PersistentClient
# 所有线程、所有请求共享这一个Client，仅初始化一次
GLOBAL_CHROMA_CLIENT = chromadb.PersistentClient(
    path=Settings.basic_settings.WARNING_KNOWLEDGE_PATH)

# 🌟 核心2：全局锁 - 读写分级（适配单Client多线程）
# 排他锁：用于写操作（add/del/drop），同一时间仅一个线程执行
# 告警管理，只有一个数据库
KB_WRITE_LOCK = threading.Lock()


class DDoc:
    def __init__(self, doc, meta, id=None):
        self.id = id
        self.doc = doc
        self.meta = meta

    def to_dict(self):
        return {"doc": self.doc, "meta": self.meta, "id": self.id}


class ChromaKBService:
    def __init__(self,
                 kb_name: str):
        self.kb_name = kb_name
        self.embed_model = get_default_embedding()
        self.embed_func = get_Embeddings(self.embed_model)
        # 🌟 单Client下：全局共享Client，直接获取/创建Collection
        self.collection: Collection = self._get_or_create_collection()

    def _get_or_create_collection(self) -> Collection:
        """获取/创建Collection，单Client下安全共享"""
        return GLOBAL_CHROMA_CLIENT.get_or_create_collection(
            name=self.kb_name,
            metadata={
                "description": f"知识库{self.kb_name} - 余弦相似度索引",
                "hnsw:space": "cosine",  # 余弦相似度（和归一化向量匹配）
                # "hnsw:m": 16,  # HNSW索引参数，平衡速度/精度
                # "hnsw:ef_construction": 100
            }
        )

    def add_docs(self, docs: List[DDoc]):
        """
        批量添加文档【写操作】- 加排他锁保证线程安全
        :param docs: 待添加的DDoc对象列表
        """
        if not docs:
            logger.warning(f"【{self.kb_name}】添加文档为空，跳过")
            return

        documents = [doc.doc for doc in docs]
        ids = [str(uuid.uuid1()) for _ in range(len(documents))]
        meta_datas = [doc.meta for doc in docs]
        embeddings = self.embed_func.embed_documents(texts=documents)
        # 🌟 写操作：加全局排他锁，禁止并发修改
        with KB_WRITE_LOCK:
            try:
                self.collection.add(
                    documents=documents,
                    ids=ids,
                    metadatas=meta_datas,
                    embeddings=embeddings  # 插入归一化后的向量
                )
                logger.info(f"【{self.kb_name}】知识库 {len(ids)} 条数据插入完成！集合文档数：{self.collection.count()}")
            except Exception as e:
                logger.error(f"【{self.kb_name}】添加文档失败：{str(e)}", exc_info=True)
                raise e  # 抛出异常，让上层处理

    def del_docs(self, ids: List[str]):
        if not ids:
            logger.warning(f"【{self.kb_name}】删除ID列表为空，跳过")
            return
        with KB_WRITE_LOCK:
            try:
                self.collection.delete(ids=ids)
                logger.info(f"【{self.kb_name}】成功删除{len(ids)}条文档，当前总文档数：{self.collection.count()}")
            except Exception as e:
                logger.error(f"【{self.kb_name}】删除文档失败：{str(e)}", exc_info=True)
                raise e

    def drop_kb(self):
        with KB_WRITE_LOCK:
            try:
                GLOBAL_CHROMA_CLIENT.delete_collection(name=self.kb_name)
                logger.info(f"【{self.kb_name}】知识库已成功删除")
            except ValueError as e:
                if "does not exist" not in str(e):
                    logger.error(f"【{self.kb_name}】删除知识库失败：{str(e)}", exc_info=True)
                    raise e
                logger.warning(f"【{self.kb_name}】知识库不存在，无需删除")
            except Exception as e:
                logger.error(f"【{self.kb_name}】删除知识库失败：{str(e)}", exc_info=True)
                raise e

    def query(self, query: str, top_k: int, score_threshold: float, filter_conditions=None) -> List[tuple[DDoc, float]]:
        query_list = [query]
        embeddings = self.embed_func.embed_documents(texts=query_list)
        results = self.collection.query(
            query_embeddings=embeddings,
            where=filter_conditions,
            n_results=top_k,
            include=["documents", "distances", "metadatas"]
        )
        res_list = []
        matched_docs = results["documents"][0]
        matched_ids = results["ids"][0]
        # 关键：ChromaDB返回的是「余弦距离」（1 - 余弦相似度），需转换为相似度分数
        cosine_distances = results["distances"][0]
        cosine_similarities = [1 - dist for dist in cosine_distances]  # 距离→相似度
        matched_metadatas = results["metadatas"][0]

        for doc, doc_id, sim, meta in zip(matched_docs, matched_ids, cosine_similarities, matched_metadatas):
            if sim >= score_threshold:
                res_list.append((DDoc(doc, meta, doc_id), sim))
            else:
                break
        return res_list

    def count(self) -> int:
        """获取知识库文档总数【读操作】"""
        return self.collection.count()


# ------------------- 多线程测试代码（验证单Client线程安全） -------------------


if __name__ == "__main__":
    def thread_add_task(kb_service: ChromaKBService, docs: List[DDoc], thread_id: int):
        """多线程添加文档任务"""
        logger.info(f"线程{thread_id}：开始执行添加文档任务")
        kb_service.add_docs(docs)
        logger.info(f"线程{thread_id}：添加文档任务执行完成")


    def thread_query_task(kb_service: ChromaKBService, query: str, thread_id: int):
        """多线程查询文档任务"""
        logger.info(f"线程{thread_id}：开始执行查询任务「{query}」")
        start = time.time()
        res = kb_service.query(query, top_k=3, score_threshold=0.5)
        cost = round(time.time() - start, 4)
        logger.info(f"线程{thread_id}：查询耗时{cost}s，匹配{len(res)}条文档")
        for ddoc, sim in res:
            logger.info(f"线程{thread_id}：相似度{sim} | 内容：{ddoc.doc[:50]}...")


    # 初始化测试知识库
    TEST_KB_NAME = "test_single_client_kb"
    kb_service = ChromaKBService(TEST_KB_NAME)

    # 构造测试文档
    test_docs1 = [
        DDoc("Python是简洁的解释型编程语言", {"category": "编程"}),
        DDoc("ChromaDB是轻量级向量数据库", {"category": "数据库"})
    ]
    test_docs2 = [
        DDoc("向量数据库通过余弦相似度实现语义检索", {"category": "数据库"}),
        DDoc("SentenceTransformer用于生成文本嵌入向量", {"category": "NLP"})
    ]
    test_docs3 = [
        DDoc("多线程编程需注意资源竞争和线程安全", {"category": "编程"}),
        DDoc("余弦相似度归一化后取值范围0~1", {"category": "算法"})
    ]

    # 1. 多线程并发添加（写操作，加锁后串行执行，安全）
    add_threads = []
    for i, docs in enumerate([test_docs1, test_docs2, test_docs3]):
        t = threading.Thread(target=thread_add_task, args=(kb_service, docs, i + 1))
        add_threads.append(t)
        t.start()
    for t in add_threads:
        t.join()
    logger.info(f"所有添加线程完成，当前知识库文档数：{kb_service.count()}")

    # 2. 多线程并发查询（读操作，无锁并行执行，高效）
    query = "向量数据库的核心原理是什么？"
    query_threads = []
    for i in range(4):  # 4个查询线程并发执行
        t = threading.Thread(target=thread_query_task, args=(kb_service, query, i + 1))
        query_threads.append(t)
        t.start()
    for t in query_threads:
        t.join()

    # 清理测试数据
    kb_service.drop_kb()
    logger.info("单Client多线程测试完成，测试知识库已删除")
