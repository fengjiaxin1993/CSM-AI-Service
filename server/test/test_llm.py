from langchain_openai import ChatOpenAI

# 阿里百练平台
llm = ChatOpenAI(
    api_key="sk-445d4654ee8e4067b447172154f0a273",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model="qwen3-32b",
    extra_body= {"enable_thinking": False}
)

# 普通openai
llm = ChatOpenAI(
    api_key="sk-445d4654ee8e4067b447172154f0a273",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model="qwen3-32b",
    extra_body={
        "chat_template_kwargs": {"enable_thinking": False},
    },
)

resp = llm.invoke("介绍一下deepseek创新点")
print(resp.content)