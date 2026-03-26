import shutil
import threading
import time
import gc
import uuid
import os
from typing import List, Tuple
import chromadb
from chromadb import QueryResult
from chromadb.config import Settings
from server.utils import get_Embeddings
from langchain.docstore.document import Document


def queryRes2docScores(results: QueryResult, score_threshold: float) -> List[Tuple[Document, float]]:
    # 解析结果
    docs_with_scores = []
    if results["documents"] and results["documents"][0]:
        documents = results["documents"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(documents)

        for doc_text, dist, meta in zip(documents, distances, metadatas):
            # ChromaDB 返回的是余弦距离，需要转换为相似度
            similarity = 1 - dist

            # 过滤低相似度结果
            if similarity >= score_threshold:
                doc = Document(page_content=doc_text, metadata=meta or {})
                docs_with_scores.append((doc, similarity))
    return docs_with_scores


class SafeChromaDB:
    """
    线程安全的 ChromaDB 封装类

    特点：
    - 所有写操作加锁
    - 支持临时库自动清理
    - LRU 缓存管理
    - 修复持久化库删除后磁盘文件清理问题
    """

    def __init__(
            self,
            embed_model: str,
            db_path: str,
            collection_name: str,  # 直接在这里指定唯一 collection
            is_temp: bool = False
    ):
        self.embed_model = embed_model
        self.embed_func = get_Embeddings(embed_model)
        self.db_path = os.path.abspath(db_path)  # 转为绝对路径，避免路径问题
        self.collection_name = collection_name  # 固定集合
        self.is_temp = is_temp
        self._lock = threading.Lock()
        self.last_used = time.time()
        self._client = None
        self._collection = None  # 缓存 collection

    def _get_collection(self):
        """单例：只创建一次 client + collection"""
        if self._collection is None:
            if self.is_temp:
                # 临时库：使用内存模式，不落盘
                self._client = chromadb.Client()
            else:
                # 持久库：使用磁盘存储
                self._client = chromadb.PersistentClient(
                    path=self.db_path,
                    settings=Settings(
                        allow_reset=True,
                        anonymized_telemetry=False
                    )
                )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": f"知识库{self.collection_name} - 余弦相似度索引",
                    "hnsw:space": "cosine",  # 余弦相似度
                }
            )
        return self._collection

    def _safe_remove_path(self, path: str, max_retries: int = 5, delay: float = 1.0):
        """
        安全删除文件/目录，处理 Windows 文件占用问题
        :param path: 要删除的路径
        :param max_retries: 最大重试次数
        :param delay: 重试间隔（秒）
        """
        if not os.path.exists(path):
            return

        # 先触发垃圾回收
        for _ in range(3):
            gc.collect()

        for retry in range(max_retries):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    # Windows 上更安全的目录删除方式
                    self._force_remove_dir(path)
                print(f"成功删除: {path}")
                return
            except (PermissionError, OSError) as e:
                if retry < max_retries - 1:
                    # 触发垃圾回收，释放文件句柄
                    gc.collect()
                    time.sleep(delay)
                else:
                    raise RuntimeError(f"删除路径失败 {path}: {str(e)}")

    def _force_remove_dir(self, path: str):
        """
        强制删除目录，处理 Windows 文件锁定问题
        """
        def on_rm_error(func, path, exc_info):
            """删除失败时的回调函数"""
            # 尝试修改文件属性后重试
            os.chmod(path, 0o777)
            func(path)

        shutil.rmtree(path, onerror=on_rm_error)

    # ====================== 写操作：需要加锁 ======================
    def add(self, ids, metadatas, texts):
        # 准备数据
        # 生成嵌入向量
        embeddings = self.embed_func.embed_documents(texts=texts)

        with self._lock:
            self.last_used = time.time()
            coll = self._get_collection()
            coll.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=texts
            )

    def add_docs(self, docs: List[Document]):
        # 准备数据
        texts = [doc.page_content for doc in docs]
        metadatas = [doc.metadata for doc in docs]
        ids = [str(uuid.uuid1()) for _ in range(len(texts))]
        # 生成嵌入向量
        embeddings = self.embed_func.embed_documents(texts=texts)

        with self._lock:
            self.last_used = time.time()
            coll = self._get_collection()
            coll.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=texts
            )

    def delete(self, ids=None, where=None):
        """删除文档【写操作】"""
        with self._lock:
            self.last_used = time.time()
            coll = self._get_collection()
            coll.delete(ids=ids, where=where)

    def delete_collection(self):
        """删除整个集合【写操作】"""
        with self._lock:
            self.last_used = time.time()
            if self._client and self._collection:
                self._client.delete_collection(self.collection_name)

    # ====================== 读操作：无需加锁 ======================
    def query(self, query: str, n_results=5):
        """查询向量【读操作】"""
        self.last_used = time.time()
        # 生成查询向量
        query_embeddings = self.embed_func.embed_documents([query])
        coll = self._get_collection()
        return coll.query(
            query_embeddings=query_embeddings,
            n_results=n_results
        )

    def search(self, query: str, top_k: int, score_threshold: float) -> List[Tuple[Document, float]]:
        """
        搜索知识库

        Args:
            query: 查询文本
            top_k: 返回数量
            score_threshold: 相似度阈值

        Returns:
            [(Document, 相似度分数), ...]
        """
        self.last_used = time.time()

        # 执行查询
        results = self.query(query, top_k)

        # 解析结果
        docs_with_scores = queryRes2docScores(results, score_threshold)
        return docs_with_scores

    def get(self, ids=None, where=None, include=None):
        """根据ID或条件获取文档【读操作】"""
        self.last_used = time.time()
        coll = self._get_collection()
        return coll.get(
            ids=ids,
            where=where,
            include=include or ["documents", "metadatas"]
        )

    def count(self) -> int:
        """获取文档数量【读操作】"""
        self.last_used = time.time()
        coll = self._get_collection()
        return coll.count()

    # ====================== 资源管理 ======================
    def drop(self):
        """
        彻底删除知识库：
        - 临时库：释放内存
        - 持久库：删除集合 + 删除磁盘文件
        """
        self._close_client()

        if not self.is_temp:
            with self._lock:
                # 多次垃圾回收确保文件句柄释放
                for _ in range(3):
                    gc.collect()
                try:
                    self._safe_remove_path(self.db_path)
                except Exception as e:
                    print(f"清理磁盘文件时警告: {str(e)}")

    def close(self):
        """
        安全关闭：只释放引用，不删除磁盘文件
        """
        self._close_client()

    def _close_client(self):
        """
        关闭 ChromaDB 客户端，确保释放所有文件句柄
        """
        with self._lock:
            # 1. 先清空 collection 引用
            self._collection = None

            # 2. 重置并释放 client
            if self._client is not None:
                try:
                    # ChromaDB 的 reset 会关闭所有连接
                    self._client.reset()
                except Exception:
                    pass

                # 显式删除 client 对象
                del self._client
                self._client = None

            # 3. 多次垃圾回收确保文件句柄完全释放
            for _ in range(3):
                gc.collect()
