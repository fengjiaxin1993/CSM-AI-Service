from langchain_openai import OpenAIEmbeddings
import os
from typing import List, Optional
import httpx
from langchain_core.embeddings import Embeddings
from openai import OpenAI


def test1():
    # 初始化 Embedding 模型
    # 注意：新版 langchain_openai 使用 api_key 而非 openai_api_key
    embeddings = OpenAIEmbeddings(
        openai_api_key="sk-445d4654ee8e4067b447172154f0a273",
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="text-embedding-v4",  # 也可以用 3-large / ada-002
        check_embedding_ctx_length=False
    )

    # ======================
    # 用法 1：对单个文本生成向量
    # ======================
    text = "这是需要生成向量的文本"
    vector = embeddings.embed_query(text)
    print("单文本向量长度:", len(vector))

    # ======================
    # 用法 2：对多个文本批量生成向量（最常用）
    # ======================
    text_list = ["文本1", "文本2", "文本3"]
    vectors = embeddings.embed_documents(text_list)
    print("批量向量数量:", len(vectors))


def test2():
    import os
    from openai import OpenAI

    client = OpenAI(
        api_key="sk-445d4654ee8e4067b447172154f0a273",  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 百炼服务的base_url
    )
    completion = client.embeddings.create(
        model="text-embedding-v4",
        input=["这是需要生成向量的文本"],
        dimensions=1024,  # 指定向量维度（仅 text-embedding-v3及 text-embedding-v4支持该参数）
        encoding_format="float"
    )
    print(completion.model_dump_json())


class DoubaoOpenAIEmbeddings(Embeddings):

    def __init__(
            self,
            model: str,
            openai_api_base: str,
            openai_api_key: str,
            timeout: float = 60,
            batch_size=128):
        self._client = OpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
            timeout=timeout,
        )

        self.model = model
        self.batch_size = batch_size

    def embed_query(self, text: str) -> List[float]:
        print(f"embed_query: {text}")

        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # return super().embed_documents(texts)
        vecs: List[List[float]] = []
        bs = self.batch_size
        for i in range(0, len(texts), bs):
            batch = texts[i:i + bs]
        resp = self._client.embeddings.create(model=self.model, input=batch)
        vecs.extend([d.embedding for d in resp.data])
        return vecs


def test3():
    embeddings = DoubaoOpenAIEmbeddings(
        model="text-embedding-v4",
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        openai_api_key="sk-445d4654ee8e4067b447172154f0a273",
    )
    print(embeddings.embed_query("你好"))


if __name__ == "__main__":
    test1()
