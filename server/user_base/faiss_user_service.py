import os
import shutil
from typing import List, Tuple

from langchain.docstore.document import Document

from server.file_rag.retrievers import VectorstoreRetrieverService
from server.utils import get_default_embedding
from settings import Settings
from server.knowledge_base.kb_cache.faiss_cache import (
    ThreadSafeFaiss,
    user_faiss_pool,
)

from server.knowledge_base.utils import get_user_vs_path, get_user_path


class FaissUserService:
    def __init__(self, user_id:str, embed_model:str = get_default_embedding()):
        self.vs_path = None
        self.vector_name = None
        self.user_id = user_id
        self.embed_model = embed_model
        self.user_path = get_user_path(self.user_id)
        self.do_init()

    def get_vs_path(self):
        return get_user_vs_path(self.user_id, self.vector_name)

    def get_user_path(self):
        return get_user_path(self.user_id)

    def load_vector_store(self) -> ThreadSafeFaiss:
        return user_faiss_pool.load_vector_store(
            user_id=self.user_id,
            vector_name=self.vector_name,
            embed_model=self.embed_model,
        )

    def save_vector_store(self):
        self.load_vector_store().save(self.vs_path)

    def do_init(self):
        self.vector_name = self.vector_name or self.embed_model.replace(":", "_")
        self.user_path = self.get_user_path()
        self.vs_path = self.get_vs_path()

    def create_user(self):
        if not os.path.exists(self.vs_path):
            os.makedirs(self.vs_path)
        self.load_vector_store()

    def drop_user(self):
        self.clear_vs()
        try:
            shutil.rmtree(self.user_path)
        except Exception:
            pass

    def search(
            self,
            query: str,
            top_k: int,
            score_threshold: float = Settings.kb_settings.SCORE_THRESHOLD,
    ) -> List[Tuple[Document, float]]:
        with self.load_vector_store().acquire() as vs:
            retriever = VectorstoreRetrieverService.from_vectorstore(
                vs,
                top_k=top_k,
                score_threshold=score_threshold,
            )
            docs = retriever.get_relevant_documents(query)
        return docs

    def add_conversation(
            self,
            message_id: str,
            query: str,
            response: str
    ):
        texts = [query]
        metadatas = [{"message_id": message_id, "response": response}]
        with self.load_vector_store().acquire() as vs:
            embeddings = vs.embeddings.embed_documents(texts)
            ids = vs.add_embeddings(
                text_embeddings=zip(texts, embeddings), metadatas=metadatas
            )
            vs.save_local(self.vs_path)

    def clear_vs(self):
        with user_faiss_pool.atomic:
            user_faiss_pool.pop((self.user_id, self.vector_name))
        try:
            shutil.rmtree(self.vs_path)
        except Exception:
            ...
        os.makedirs(self.vs_path, exist_ok=True)


if __name__ == "__main__":
    faissService = FaissUserService("test")
    texts = ["2022年2月2号，美国国防部宣布：将向欧洲增派部队，应对俄乌边境地区的紧张局势.",
             "2月17号，乌克兰军方称：东部民间武装向政府军控制区发动炮击，而东部民间武装则指责乌政府军先动用了重型武器发动袭击，乌东地区紧张局势持续升级"]
    # faissService.add_conversation("m1", texts[0], "1")
    # faissService.add_conversation("m2", texts[1], "2")
    print(faissService.search("美国国防部宣布：将向欧洲增派部队",top_k=2,score_threshold=0.6))
