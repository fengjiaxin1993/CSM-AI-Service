import uuid

from fastapi import Body
from langchain_classic.callbacks import AsyncIteratorCallbackHandler
from sse_starlette.sse import EventSourceResponse

from server.api_server.api_schemas import OpenAIChatOutput
from server.callback_handler.message_callback_handler import MessageCallbackHandler
from server.chat.utils import History
from server.db.repository import add_message_to_db, filter_message
from langchain_core.prompts import ChatPromptTemplate
from typing import AsyncIterable
import asyncio
from typing import List, Optional
from server.utils import (
    get_ChatOpenAI,
    get_prompt_template,
    wrap_done
)
from settings import Settings


async def mem_chat(
        query: str = Body("", description="用户输入", examples=["你好"]),
        conversation_id: str = Body("", description="对话框id"),
        history_len: int = Body(3, description="从数据库中取历史消息的数量"),
        stream: bool = Body(False, description="流式输出"),
):
    model_name = Settings.model_settings.DEFAULT_LLM_MODEL
    temperature = Settings.model_settings.TEMPERATURE
    max_tokens = Settings.model_settings.MAX_TOKENS

    async def chat_iterator() -> AsyncIterable[str]:
        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback]

        # 负责保存llm response到message db
        message_id = add_message_to_db(query=query, conversation_id=conversation_id)
        message_callback = MessageCallbackHandler(conversation_id=conversation_id, message_id=message_id,
                                                  query=query)
        callbacks.append(message_callback)
        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks,
        )

        if conversation_id and history_len > 0:  # 根据user_id 获取历史对话信息
            messages = filter_message(
                conversation_id=conversation_id, limit=history_len, asc=False
            )
            # 转换为正序
            messages = list(reversed(messages))
            history = []
            for message in messages:
                history.append(History(**{"role": "user", "content": message["query"]}))
            prompt_template = get_prompt_template("llm_model", "default")
            system_msg = History(role="assistant",
                                 content="你是一个知识渊博的助手，请帮助用户解答问题。").to_msg_template(False)
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
