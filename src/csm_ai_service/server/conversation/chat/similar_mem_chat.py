import uuid
from fastapi import Body
from langchain_classic.callbacks import AsyncIteratorCallbackHandler
from sse_starlette.sse import EventSourceResponse

from csm_ai_service.server.api_server.api_schemas import OpenAIChatOutput
from csm_ai_service.server.conversation.callback_handler.user_callback_handler import UserCallbackHandler
from csm_ai_service.server.conversation.chat.utils import History
from langchain_core.prompts import ChatPromptTemplate
from typing import AsyncIterable
import asyncio

from csm_ai_service.server.conversation.user_base.faiss_user_service import FaissUserService
from csm_ai_service.server.utils import (
    get_ChatOpenAI,
    get_prompt_template,
    wrap_done
)
from csm_ai_service.settings import Settings
from csm_ai_service.server.db.repository import add_user_message_to_db


async def similar_mem_chat(
        query: str = Body(..., description="用户输入", examples=["你好"]),
        user_id: str = Body("", description="用户ID"),
        stream: bool = Body(False, description="流式输出"),
):
    top_k = Settings.kb_settings.VECTOR_SEARCH_TOP_K
    score_threshold = Settings.kb_settings.SCORE_THRESHOLD
    model_name = Settings.model_settings.DEFAULT_LLM_MODEL
    temperature = Settings.model_settings.TEMPERATURE
    max_tokens = Settings.model_settings.MAX_TOKENS

    async def chat_iterator() -> AsyncIterable[str]:
        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback]

        # 负责保存llm response到message db
        message_id = add_user_message_to_db(chat_type="llm_chat", query=query, user_id=user_id)
        user_callback = UserCallbackHandler(user_id=user_id, message_id=message_id,
                                            chat_type="llm_chat",
                                            query=query)
        callbacks.append(user_callback)
        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks,
        )

        if user_id and top_k > 0:  # 根据user_id 获取历史对话信息
            service = FaissUserService(user_id)
            docs = service.search(query, top_k=top_k, score_threshold=score_threshold)
            history = []
            for doc in docs:
                history.append(History(**{"role": "user", "content": doc.page_content}))

            prompt_template = get_prompt_template("llm_model", "default")
            system_msg = History(role="assistant", content="你是一个知识渊博的助手，请帮助用户解答问题。").to_msg_template(False)
            input_msg = History(role="user", content=prompt_template).to_msg_template(False)
            chat_prompt = ChatPromptTemplate.from_messages([system_msg] +
                    [i.to_msg_template(False) for i in history] + [input_msg])

        else:  # 不考虑任何历史记录
            prompt_template = get_prompt_template("llm_model", "default")
            input_msg = History(role="user", content=prompt_template).to_msg_template(False)
            chat_prompt = ChatPromptTemplate.from_messages([input_msg])

        chain = chat_prompt | model
        full_chain = {"input": lambda x: x["input"]} | chain

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            full_chain.ainvoke({"input": query}),
            callback.done),
        )

        if stream:
            async for token in callback.aiter():
                ret = OpenAIChatOutput(
                    id=f"chat{uuid.uuid4()}",
                    object="chat.completion.chunk",
                    content=token,
                    role="assistant",
                    model=model_name,
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
                model=model_name,
            )
            yield ret.model_dump_json()
        await task

    if stream:
        return EventSourceResponse(chat_iterator())
    else:
        return await chat_iterator().__anext__()

