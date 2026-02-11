from pathlib import Path
import sys
import typing as t
from pydantic_settings_file import *

# chatchat 数据目录，必须通过环境变量设置。如未设置则自动使用当前目录。
CHATCHAT_ROOT = Path(".").resolve()


class BasicSettings(BaseFileSettings):
    """
    服务器基本配置信息
    除 log_verbose/HTTPX_DEFAULT_TIMEOUT 修改后即时生效，其它配置项修改后都需要重启服务器才能生效
    """

    model_config = SettingsConfigDict(yaml_file=CHATCHAT_ROOT / "basic_settings.yaml")
    log_verbose: bool = False
    """是否开启日志详细信息"""

    LOG_FORMAT: str = "%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s"
    """日志格式"""

    HTTPX_DEFAULT_TIMEOUT: float = 300
    """httpx 请求默认超时时间（秒）。如果加载模型或对话较慢，出现超时错误，可以适当加大该值。"""

    # @computed_field
    @cached_property
    def PACKAGE_ROOT(self) -> Path:
        """代码根目录"""
        return Path(__file__).parent

    # @computed_field
    @cached_property
    def DATA_PATH(self) -> Path:
        """用户数据根目录"""
        p = CHATCHAT_ROOT / "data"
        return p

    # @computed_field
    @cached_property
    def NLTK_DATA_PATH(self) -> Path:
        """nltk 模型存储路径"""
        p = self.DATA_PATH / "nltk_data"
        return p

    # @computed_field
    @cached_property
    def LOG_PATH(self) -> Path:
        """日志存储路径"""
        p = self.DATA_PATH / "logs"
        return p

    # @computed_field
    @cached_property
    def BASE_TEMP_DIR(self) -> Path:
        """临时文件目录，主要用于文件对话"""
        p = self.DATA_PATH / "temp"
        return p

    KB_ROOT_PATH: str = str(CHATCHAT_ROOT / "data/knowledge_base")
    """知识库默认存储路径"""

    WARNING_KNOWLEDGE_PATH: str = str(CHATCHAT_ROOT / "data/warning_knowledge")
    """告警知识库默认存储路径， 与通用知识库不通，有特定处理"""

    USER_ROOT_PATH: str = str(CHATCHAT_ROOT / "data/user")
    """记录用户历史对话记录的存储路径"""

    DB_ROOT_PATH: str = str(CHATCHAT_ROOT / "data/knowledge_base/info.db")
    """数据库默认存储路径。如果使用sqlite，可以直接修改DB_ROOT_PATH；如果使用其它数据库，请直接修改SQLALCHEMY_DATABASE_URI。"""

    SQLALCHEMY_DATABASE_URI: str = "sqlite:///" + str(CHATCHAT_ROOT / "data/knowledge_base/info.db")
    """知识库信息数据库连接URI"""

    OPEN_CROSS_DOMAIN: bool = True
    """API 是否开启跨域"""

    DEFAULT_BIND_HOST: str = "0.0.0.0" if sys.platform != "win32" else "127.0.0.1"
    """
    各服务器默认绑定host。如改为"0.0.0.0"需要修改下方所有XX_SERVER的host
    Windows 下 WEBUI 自动弹出浏览器时，如果地址为 "0.0.0.0" 是无法访问的，需要手动修改地址栏
    """

    API_SERVER: dict = {"host": DEFAULT_BIND_HOST, "port": 7861}
    """API 服务器地址"""

    WEBUI_SERVER: dict = {"host": DEFAULT_BIND_HOST, "port": 8501}
    """WEBUI 服务器地址"""

    def make_dirs(self):
        '''创建所有数据目录'''
        for p in [
            self.DATA_PATH,
            self.NLTK_DATA_PATH,
            self.LOG_PATH,
            self.BASE_TEMP_DIR,
        ]:
            p.mkdir(parents=True, exist_ok=True)
        Path(self.KB_ROOT_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.USER_ROOT_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.WARNING_KNOWLEDGE_PATH).mkdir(parents=True, exist_ok=True)


class KBSettings(BaseFileSettings):
    """知识库相关配置"""

    model_config = SettingsConfigDict(yaml_file=CHATCHAT_ROOT / "kb_settings.yaml")

    DEFAULT_KNOWLEDGE_BASE: str = "samples"
    """默认使用的知识库"""

    WARNING_KNOWLEDGE: str = "warning"
    """默认的告警知识库"""

    DEFAULT_VS_TYPE: str = "faiss"
    """默认使用faiss向量数据库"""

    CACHED_VS_NUM: int = 1
    """缓存向量库数量（针对FAISS）"""

    CACHED_MEMO_VS_NUM: int = 10
    """缓存临时向量库数量（针对FAISS），用于文件对话"""

    CACHED_USER_VS_NUM: int = 3
    """缓存用户数（针对FAISS），用于记忆用户能力"""

    CHUNK_SIZE: int = 750
    """知识库中单段文本长度(不适用MarkdownHeaderTextSplitter)"""

    OVERLAP_SIZE: int = 150
    """知识库中相邻文本重合长度(不适用MarkdownHeaderTextSplitter)"""

    VECTOR_SEARCH_TOP_K: int = 3
    """知识库匹配向量数量"""

    SCORE_THRESHOLD: float = 0.3
    """知识库匹配相关度阈值，采用相似度，取值范围在-1-1之间，SCORE越大，相关度越高，取到-1相当于不筛选，建议设置在0.3左右"""

    ZH_TITLE_ENHANCE: bool = False
    """是否开启中文标题加强，以及标题增强的相关配置"""

    KB_INFO: t.Dict[str, str] = {"samples": "关于本项目issue的解答"}
    """每个知识库的初始化介绍"""

    text_splitter_dict: t.Dict[str, t.Dict[str, t.Any]] = {
        "ChineseRecursiveTextSplitter": {
            "source": "",
            "tokenizer_name_or_path": "",
        },
        "MarkdownHeaderTextSplitter": {
            "headers_to_split_on": [
                ("#", "head1"),
                ("##", "head2"),
                ("###", "head3"),
                ("####", "head4"),
            ]
        },
    }
    """
    TextSplitter配置项，如果你不明白其中的含义，就不要修改。
    source 如果选择tiktoken则使用openai的方法 "huggingface"
    """

    TEXT_SPLITTER_NAME: str = "ChineseRecursiveTextSplitter"
    """TEXT_SPLITTER 名称"""


class PlatformConfig(MyBaseModel):
    """模型加载平台配置"""

    platform_name: str = "ollama"
    """平台名称"""

    platform_type: t.Literal["ollama", "openai"] = "ollama"
    """平台类型"""

    api_base_url: str = "http://127.0.0.1:11434/v1"
    """openai api url"""

    api_key: str = "EMPTY"
    """api key if available"""

    llm_models: t.Union[t.Literal["auto"], t.List[str]] = []
    """该平台支持的大语言模型列表"""

    embed_models: t.Union[t.Literal["auto"], t.List[str]] = []
    """该平台支持的嵌入模型列表"""


class ApiModelSettings(BaseFileSettings):
    """模型配置项"""

    model_config = SettingsConfigDict(yaml_file=CHATCHAT_ROOT / "model_settings.yaml")

    DEFAULT_LLM_MODEL: str = "qwen2.5:0.5b"
    """默认选用的 LLM 名称"""

    DEFAULT_EMBEDDING_MODEL: str = "quentinz/bge-small-zh-v1.5"
    """默认选用的 Embedding 名称"""

    HISTORY_LEN: int = 3
    """默认历史对话轮数"""

    MAX_TOKENS: t.Optional[int] = 4096  # TODO: 似乎与 LLM_MODEL_CONFIG 重复了
    """大模型最长支持的长度，如果不填写，则使用模型默认的最大长度，如果填写，则为用户设定的最大长度"""

    TEMPERATURE: float = 0.7
    """LLM通用对话参数"""

    LLM_MODEL_CONFIG: t.Dict[str, t.Dict] = {
        "llm_model": {
            "model": "",
            "prompt_name": "default",
        }
    }
    """
    LLM模型配置，包括了不同模态初始化参数。
    `model` 如果留空则自动使用 DEFAULT_LLM_MODEL
    """

    MODEL_PLATFORMS: t.List[PlatformConfig] = [
        PlatformConfig(**{
            "platform_name": "ollama",
            "platform_type": "ollama",
            "api_base_url": "http://192.168.88.1:11434/v1",
            "api_key": "EMPTY",
            "llm_models": [
                "qwen2.5:0.5b",
            ],
            "embed_models": [
                "quentinz/bge-small-zh-v1.5",
            ],
        }),
        PlatformConfig(**{
            "platform_name": "openai",
            "platform_type": "openai",
            "api_base_url": "https://api.openai.com/v1",
            "api_key": "sk-proj-",
            "llm_models": [
                "gpt-4o",
                "gpt-3.5-turbo",
            ],
            "embed_models": [
                "text-embedding-3-small",
                "text-embedding-3-large",
            ],
        }),
    ]
    """模型平台配置"""


class PromptSettings(BaseFileSettings):
    """Prompt 模板.使用 jinja2 格式"""

    model_config = SettingsConfigDict(yaml_file=CHATCHAT_ROOT / "prompt_settings.yaml",
                                      json_file=CHATCHAT_ROOT / "prompt_settings.json",
                                      extra="allow")

    llm_model: dict = {
        "default": "{{input}}",
        "with_history": (
            "这是人类和 AI 之间的友好对话。\n"
            "AI非常健谈并从其上下文中提供了大量的具体细节。\n\n"
            "当前对话:\n"
            "{{history}}\n"
            "Human: {{input}}\n"
            "AI:"
        ),
    }
    '''告警电力解析提示词'''
    warning: dict = {
        "default": (
            "你是电力行业告警处置报告审核专家，严格遵循《电力监控系统安全防护规定》《网络安全法》，审核以下报告:\n"
            "【研判维度】\n"
            "1. 处置合规性：处置步骤是否清晰可追溯，处置结果是否明确\n"
            "2. 原因分析有效性：原因是否明确，无模糊表述\n"
            "3. 整改闭环：整改措施具体可执行\n"
            "4. 历史一致性：与同类告警处置方案无矛盾，差异需说明合理原因\n"
            "【同类电力告警参考】\n"
            "{{retrieved_info}}\n"
            "【本次待审核报告】\n"
            "{{report_info}}\n"

            "【输出要求】严格按以下JSON格式返回，key的字段一定要匹配，语言贴合电力运维场景：\n"
            "{"
            "'audit_result': '通过/驳回/需人工复核',\n"
            "'audit_details': '从不同维度说明审核结果',\n"
            "'summary': '报告核心总结（100字内，含告警类型、处置结果、合规情况）',\n"
            "'reject_reason': '驳回需说明具体修改要求，否则为空',\n"
            "'power_suggestion': '电力行业专属优化建议'\n"
            "} ")
    }

    rag: dict = {
        "default": (
            "【指令】根据已知信息，简洁和专业的来回答问题。"
            "如果无法从中得到答案，请说 “根据已知信息无法回答该问题”，不允许在答案中添加编造成分，答案请使用中文。\n\n"
            "【已知信息】{{context}}\n\n"
            "【问题】{{question}}\n"
        ),
        "empty": (
            "请你回答我的问题:\n"
            "{{question}}"
        ),
    }
    '''RAG 用模板，可用于知识库问答、文件对话'''


class SettingsContainer:
    CHATCHAT_ROOT = CHATCHAT_ROOT

    basic_settings: BasicSettings = settings_property(BasicSettings())
    kb_settings: KBSettings = settings_property(KBSettings())
    model_settings: ApiModelSettings = settings_property(ApiModelSettings())
    prompt_settings: PromptSettings = settings_property(PromptSettings())

    def create_all_templates(self):
        self.basic_settings.create_template_file(write_file=True)
        self.kb_settings.create_template_file(write_file=True)
        self.model_settings.create_template_file(sub_comments={
            "MODEL_PLATFORMS": {"model_obj": PlatformConfig(),
                                "is_entire_comment": True}},
            write_file=True)
        self.prompt_settings.create_template_file(write_file=True, file_format="yaml")

    def set_auto_reload(self, flag: bool = True):
        self.basic_settings.auto_reload = flag
        self.kb_settings.auto_reload = flag
        self.model_settings.auto_reload = flag
        self.prompt_settings.auto_reload = flag


Settings = SettingsContainer()

if __name__ == "__main__":
    Settings.create_all_templates()
