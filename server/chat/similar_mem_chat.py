import uuid
from fastapi import Body
from sse_starlette.sse import EventSourceResponse

from server.api_server.api_schemas import OpenAIChatOutput
from server.callback_handler.user_callback_handler import UserCallbackHandler
from server.chat.utils import History
from server.db.repository import add_message_to_db
from langchain.callbacks import AsyncIteratorCallbackHandler
from typing import AsyncIterable
import asyncio
from langchain.prompts.chat import ChatPromptTemplate
from typing import List, Optional

from server.user_base.faiss_user_service import FaissUserService
from server.utils import (
    get_ChatOpenAI,
    get_prompt_template,
    wrap_done,
    get_default_llm,
)
from settings import Settings


async def similar_mem_chat(
        messages: List[dict] = Body(
            [],
            description="消息",
            examples=[
                [
                    {"role": "user", "content": "介绍一下deepSeek创新点"}
                ]
            ],
        ),
        user_id: str = Body("", description="用户ID"),
        top_k: int = Body(3, description="相似的对话"),
        score_threshold: float = Body(Settings.kb_settings.SCORE_THRESHOLD, description="语义相似度，越大越相似", ge=0.0, le=1.0),
        stream: bool = Body(False, description="流式输出"),
        model_name: str = Body(Settings.model_settings.DEFAULT_LLM_MODEL, description="LLM 模型名称。"),
        temperature: float = Body(Settings.model_settings.TEMPERATURE, description="LLM 采样温度", ge=0.0, le=2.0),
        max_tokens: int = Body(Settings.model_settings.MAX_TOKENS, description="LLM最大token数配置,一定要大于0",
                               example=4096),
):
    query = messages[-1]["content"]

    async def chat_iterator() -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback]

        # 负责保存llm response到message db
        message_id = add_message_to_db(chat_type="llm_chat", query=query, user_id=user_id)
        user_callback = UserCallbackHandler(user_id=user_id, message_id=message_id,
                                            chat_type="llm_chat",
                                            query=query)
        callbacks.append(user_callback)
        # 判断是否传入 max_tokens 的值, 如果传入就按传入的赋值(api 调用且赋值), 如果没有传入则按照初始化配置赋值(ui 调用或 api 调用未赋值)
        max_tokens_value = max_tokens if max_tokens is not None and max_tokens > 0 else Settings.model_settings.MAX_TOKENS
        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens_value,
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

