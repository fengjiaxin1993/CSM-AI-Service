from __future__ import annotations
import asyncio
import uuid
from typing import AsyncIterable
from fastapi import Body
from fastapi.concurrency import run_in_threadpool
from langchain_classic.callbacks import AsyncIteratorCallbackHandler
from sse_starlette.sse import EventSourceResponse
from langchain_core.prompts import ChatPromptTemplate
from csm_ai_service.settings import Settings
from csm_ai_service.server.api_server.api_schemas import OpenAIChatOutput
from csm_ai_service.server.conversation.chat.utils import History
from csm_ai_service.server.conversation.knowledge_base.kb_service.base import KBServiceFactory
from csm_ai_service.server.conversation.knowledge_base.kb_doc_api import search_docs
from csm_ai_service.server.conversation.knowledge_base.utils import format_reference
from csm_ai_service.server.utils import (wrap_done, get_ChatOpenAI,
                          BaseResponse, get_prompt_template,)

from csm_ai_service.server.utils import build_logger

logger = build_logger()


async def kb_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
                  kb_name: str = Body("",
                                      description="知识库名称",
                                      examples=["samples"]),
                  stream: bool = Body(True, description="流式输出"),
                  return_direct: bool = Body(False, description="直接返回检索结果，不送入 LLM"),
                  ):
    top_k = Settings.kb_settings.VECTOR_SEARCH_TOP_K
    score_threshold = Settings.kb_settings.SCORE_THRESHOLD
    model = Settings.model_settings.DEFAULT_LLM_MODEL
    temperature = Settings.model_settings.TEMPERATURE
    max_tokens = Settings.model_settings.MAX_TOKENS
    prompt_name = "default"
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

    async def knowledge_base_chat_iterator() -> AsyncIterable[str]:
        nonlocal prompt_name
        docs = await run_in_threadpool(search_docs,
                                       query=query,
                                       knowledge_base_name=kb_name,
                                       top_k=top_k,
                                       score_threshold=score_threshold,
                                       file_name="",
                                       metadata={})
        source_documents = format_reference(kb_name, docs)
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
        chat_prompt = ChatPromptTemplate.from_messages([input_msg])

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
