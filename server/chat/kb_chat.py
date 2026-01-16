from __future__ import annotations
import asyncio
import os
import uuid
from typing import AsyncIterable, List, Optional, Literal
from fastapi import Body, Request, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.prompts.chat import ChatPromptTemplate

from server.knowledge_base.kb_cache.faiss_cache import memo_faiss_pool
from settings import Settings
from server.api_server.api_schemas import OpenAIChatOutput
from server.chat.utils import History
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.knowledge_base.kb_doc_api import search_docs, search_temp_docs
from server.knowledge_base.utils import format_reference, KnowledgeFile
from server.utils import (wrap_done, get_ChatOpenAI, get_default_llm,
                          BaseResponse, get_prompt_template, run_in_thread_pool, get_temp_dir)

from server.utils import build_logger

logger = build_logger()


def _parse_files_in_thread(
        files: List[UploadFile],
        dir: str,
        zh_title_enhance: bool,
        chunk_size: int,
        chunk_overlap: int,
):
    """
    通过多线程将上传的文件保存到对应目录内。
    生成器返回保存结果：[success or error, filename, msg, docs]
    """

    def parse_file(file: UploadFile) -> dict:
        """
        保存单个文件。
        """
        try:
            filename = file.filename
            file_path = os.path.join(dir, filename)
            file_content = file.file.read()  # 读取上传文件的内容

            if not os.path.isdir(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            with open(file_path, "wb") as f:
                f.write(file_content)
            kb_file = KnowledgeFile(filename=filename, knowledge_base_name="temp")
            kb_file.filepath = file_path
            docs = kb_file.file2text(
                zh_title_enhance=zh_title_enhance,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            return True, filename, f"成功上传文件 {filename}", docs
        except Exception as e:
            msg = f"{filename} 文件上传失败，报错信息为: {e}"
            return False, filename, msg, []

    params = [{"file": file} for file in files]
    for result in run_in_thread_pool(parse_file, params=params):
        yield result


def upload_temp_docs(
        files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
        prev_id: str = Form(None, description="前知识库ID"),
        chunk_size: int = Form(Settings.kb_settings.CHUNK_SIZE, description="知识库中单段文本最大长度"),
        chunk_overlap: int = Form(Settings.kb_settings.OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
        zh_title_enhance: bool = Form(Settings.kb_settings.ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
) -> BaseResponse:
    """
    将文件保存到临时目录，并进行向量化。
    返回临时目录名称作为ID，同时也是临时向量库的ID。
    """
    if prev_id is not None:
        memo_faiss_pool.pop(prev_id)

    failed_files = []
    documents = []
    path, id = get_temp_dir(prev_id)
    for success, file, msg, docs in _parse_files_in_thread(
            files=files,
            dir=path,
            zh_title_enhance=zh_title_enhance,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
    ):
        if success:
            documents += docs
        else:
            failed_files.append({file: msg})
    try:
        with memo_faiss_pool.load_vector_store(kb_name=id).acquire() as vs:
            vs.add_documents(documents)
    except Exception as e:
        logger.error(f"Failed to add documents to faiss: {e}")

    return BaseResponse(data={"id": id, "failed_files": failed_files})


async def kb_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
                  mode: Literal["local_kb", "temp_kb", "search_engine"] = Body("local_kb", description="知识来源"),
                  kb_name: str = Body("",
                                      description="mode=local_kb时为知识库名称；temp_kb时为临时知识库ID，search_engine时为搜索引擎名称",
                                      examples=["samples"]),
                  top_k: int = Body(Settings.kb_settings.VECTOR_SEARCH_TOP_K, description="匹配向量数"),
                  score_threshold: float = Body(
                      Settings.kb_settings.SCORE_THRESHOLD,
                      description="知识库匹配相关度阈值，取值范围在-1-1之间，SCORE越大，相关度越高，取到-1相当于不筛选，建议设置在0.3左右",
                      ge=-1,
                      le=1,
                  ),
                  history: List[History] = Body(
                      [],
                      description="历史对话",
                      examples=[[
                          {"role": "user",
                           "content": "我们来玩成语接龙，我先来，生龙活虎"},
                          {"role": "assistant",
                           "content": "虎头虎脑"}]]
                  ),
                  stream: bool = Body(True, description="流式输出"),
                  model: str = Body(get_default_llm(), description="LLM 模型名称。"),
                  temperature: float = Body(Settings.model_settings.TEMPERATURE, description="LLM 采样温度", ge=0.0,
                                            le=2.0),
                  max_tokens: Optional[int] = Body(
                      Settings.model_settings.MAX_TOKENS,
                      description="限制LLM生成Token数量，默认None代表模型最大值"
                  ),
                  prompt_name: str = Body(
                      "default",
                      description="使用的prompt模板名称(在prompt_settings.yaml中配置)"
                  ),
                  return_direct: bool = Body(False, description="直接返回检索结果，不送入 LLM"),
                  request: Request = None,
                  ):
    if mode == "local_kb":
        kb = KBServiceFactory.get_service_by_name(kb_name)
        if kb is None:
            return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

    async def knowledge_base_chat_iterator() -> AsyncIterable[str]:
        nonlocal history, prompt_name

        history = [History.from_data(h) for h in history]

        if mode == "local_kb":
            docs = await run_in_threadpool(search_docs,
                                           query=query,
                                           knowledge_base_name=kb_name,
                                           top_k=top_k,
                                           score_threshold=score_threshold,
                                           file_name="",
                                           metadata={})
            source_documents = format_reference(kb_name, docs, request.base_url)
        elif mode == "temp_kb":
            docs = await run_in_threadpool(search_temp_docs,
                                           kb_name,
                                           query=query,
                                           top_k=top_k,
                                           score_threshold=score_threshold)
            source_documents = format_reference(kb_name, docs, request.base_url)
        else:
            docs = []
            source_documents = []
        if return_direct:
            yield OpenAIChatOutput(
                id=f"chat{uuid.uuid4()}",
                model=None,
                object="chat.completion",
                content="",
                role="assistant",
                finish_reason="stop",
                docs=source_documents,
            ).model_dump_json()
            return

        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback]

        llm = get_ChatOpenAI(
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks,
        )
        context = "\n\n".join([doc["page_content"] for doc in docs])

        if len(docs) == 0:  # 如果没有找到相关文档，使用empty模板
            prompt_name = "empty"
        prompt_template = get_prompt_template("rag", prompt_name)
        input_msg = History(role="user", content=prompt_template).to_msg_template(False)
        chat_prompt = ChatPromptTemplate.from_messages(
            [i.to_msg_template() for i in history] + [input_msg])

        chain = chat_prompt | llm

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.ainvoke({"context": context, "question": query}),
            callback.done),
        )

        if len(source_documents) == 0:  # 没有找到相关文档
            source_documents.append(f"<span style='color:red'>未找到相关文档,该回答为大模型自身能力解答！</span>")

        if stream:
            # yield documents first
            ret = OpenAIChatOutput(
                id=f"chat{uuid.uuid4()}",
                object="chat.completion.chunk",
                content="",
                role="assistant",
                model=model,
                docs=source_documents,
            )
            yield ret.model_dump_json()

            async for token in callback.aiter():
                ret = OpenAIChatOutput(
                    id=f"chat{uuid.uuid4()}",
                    object="chat.completion.chunk",
                    content=token,
                    role="assistant",
                    model=model,
                )
                yield ret.model_dump_json()
        else:
            answer = ""
            async for token in callback.aiter():
                answer += token
            ret = OpenAIChatOutput(
                id=f"chat{uuid.uuid4()}",
                object="chat.completion",
                content=answer,
                role="assistant",
                model=model,
            )
            yield ret.model_dump_json()
        await task

    if stream:
        return EventSourceResponse(knowledge_base_chat_iterator())
    else:
        return await knowledge_base_chat_iterator().__anext__()
