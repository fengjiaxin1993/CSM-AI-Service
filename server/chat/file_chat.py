from __future__ import annotations
import asyncio
import os
import uuid
from typing import AsyncIterable, List, Optional, Literal
from fastapi import Body, Request, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from langchain_classic.callbacks import AsyncIteratorCallbackHandler
from sse_starlette.sse import EventSourceResponse
from langchain_core.prompts import ChatPromptTemplate

from server.callback_handler.message_callback_handler import MessageCallbackHandler
from server.db.repository import add_message_to_db
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

    def parse_file(file: UploadFile) -> tuple:
        """
        保存单个文件。
        """
        filename = None
        try:
            filename = file.filename
            file_path = os.path.join(str(dir), str(filename))
            file_content = file.file.read()  # 读取上传文件的内容

            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.isdir(parent_dir):
                os.makedirs(parent_dir)
            with open(file_path, "wb") as f:
                f.write(file_content)
            kb_file = KnowledgeFile(filename=filename, knowledge_base_name="temp")
            kb_file.filepath = file_path
            docs = kb_file.file2text(
                zh_title_enhance=zh_title_enhance,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            return (True, filename, f"成功上传文件 {filename}", docs)
        except Exception as e:
            if filename is None:
                filename = getattr(file, 'filename', 'unknown')
            msg = f"{filename} 文件上传失败，报错信息为: {e}"
            return (False, filename, msg, [])

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
    if not prev_id:
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

    return BaseResponse(data={"file_id": id, "failed_files": failed_files})


async def file_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
                    file_id: str = Body("", description="上传文件id", examples=["samples"]),
                    conversation_id: str = Body("", description="对话框id"),
                    stream: bool = Body(True, description="流式输出"),
                    ):
    top_k = Settings.kb_settings.VECTOR_SEARCH_TOP_K
    score_threshold = Settings.kb_settings.SCORE_THRESHOLD
    model = Settings.model_settings.DEFAULT_LLM_MODEL
    temperature = Settings.model_settings.TEMPERATURE
    max_tokens = Settings.model_settings.MAX_TOKENS
    prompt_name = "default"
    file_names = []
    if file_id:  # 如果指定的临时目录已存在，直接返回
        path = os.path.join(Settings.basic_settings.BASE_TEMP_DIR, file_id)
        if os.path.isdir(path):
            file_names = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

    async def file_chat_iterator() -> AsyncIterable[str]:

        meta_data = {"file_id": file_id, "file_names": file_names}
        message_id = add_message_to_db(query=query, conversation_id=conversation_id, metadata=meta_data)
        message_callback = MessageCallbackHandler(conversation_id=conversation_id, message_id=message_id, query=query)
        nonlocal prompt_name

        docs = await run_in_threadpool(search_temp_docs,
                                       knowledge_id=file_id,
                                       query=query,
                                       top_k=top_k,
                                       score_threshold=score_threshold)

        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback, message_callback]

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
        chat_prompt = ChatPromptTemplate.from_messages([input_msg])

        chain = chat_prompt | llm

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.ainvoke({"context": context, "question": query}),
            callback.done),
        )

        if stream:
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
        return EventSourceResponse(file_chat_iterator())
    else:
        return await file_chat_iterator().__anext__()
