import uuid
from fastapi import Body
from langchain_classic.callbacks import AsyncIteratorCallbackHandler
from langchain_core.prompts import ChatPromptTemplate
from sse_starlette.sse import EventSourceResponse
from server.api_server.api_schemas import OpenAIChatOutput
from server.chat.utils import History
from typing import AsyncIterable
import asyncio
from server.utils import (
    get_ChatOpenAI,
    get_prompt_template,
    wrap_done
)
from settings import Settings


async def chat(
        query: str = Body("介绍一下deepSeek创新点", description="用户问题"),
        stream: bool = Body(False, description="流式输出")
):
    model_name = Settings.model_settings.DEFAULT_LLM_MODEL,

    async def chat_iterator() -> AsyncIterable[str]:
        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback]

        model = get_ChatOpenAI(
            model_name=Settings.model_settings.DEFAULT_LLM_MODEL,
            temperature=Settings.model_settings.TEMPERATURE,
            max_tokens=Settings.model_settings.MAX_TOKENS,
            callbacks=callbacks,
        )

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
