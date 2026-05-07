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

    @cached_property
    def TEMPLATE_PATH(self) -> Path:
        """nltk 模型存储路径"""
        p = self.DATA_PATH / "template_file"
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

    @cached_property
    def WARNING_NOTICE_DIR(self) -> Path:
        """整改通知单路径"""
        p = self.DATA_PATH / "warning_notice"
        return p

    KB_ROOT_PATH: str = str(CHATCHAT_ROOT / "data/knowledge_base")
    """知识库默认存储路径"""

    USER_ROOT_PATH: str = str(CHATCHAT_ROOT / "data/user")
    """记录用户历史对话记录的存储路径"""

    WARNING_NOTICE_PATH: str = str(CHATCHAT_ROOT / "data/warning_notice")
    """记录存储告警整改通知单的目录"""

    DB_ROOT_PATH: str = str(CHATCHAT_ROOT / "data/knowledge_base/info.db")
    """数据库默认存储路径。如果使用sqlite，可以直接修改DB_ROOT_PATH；如果使用其它数据库，请直接修改SQLALCHEMY_DATABASE_URI。"""

    SQLALCHEMY_DATABASE_URI: str = "sqlite:///" + str(CHATCHAT_ROOT / "data/knowledge_base/info.db")
    """知识库信息数据库连接URI"""

    OPEN_CROSS_DOMAIN: bool = True
    """API 是否开启跨域"""

    DEBUG: bool = True
    """doc的 api 是否web页面可以查看"""

    PRINT_AGENT: bool = True
    """打印agent执行的中间状态"""

    DEFAULT_BIND_HOST: str = "0.0.0.0" if sys.platform != "win32" else "127.0.0.1"
    """
    各服务器默认绑定host。如改为"0.0.0.0"需要修改下方所有XX_SERVER的host
    Windows 下 WEBUI 自动弹出浏览器时，如果地址为 "0.0.0.0" 是无法访问的，需要手动修改地址栏
    """

    API_SERVER: dict = {"host": DEFAULT_BIND_HOST, "port": 7861}
    """API 服务器地址"""

    def make_dirs(self):
        '''创建所有数据目录'''
        for p in [
            self.DATA_PATH,
            self.NLTK_DATA_PATH,
            self.LOG_PATH,
            self.BASE_TEMP_DIR,
            self.TEMPLATE_PATH
        ]:
            p.mkdir(parents=True, exist_ok=True)
        Path(self.KB_ROOT_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.USER_ROOT_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.WARNING_NOTICE_PATH).mkdir(parents=True, exist_ok=True)


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

    VECTOR_SEARCH_TOP_K: int = 5
    """知识库匹配向量数量"""

    SCORE_THRESHOLD: float = 0.2
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

    llm_base_url: str = "http://127.0.0.1:11434/v1"
    """openai api url"""

    embedding_base_url: str = "http://127.0.0.1:11434/v1"
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

    IS_ALIYUN_PLATFORM: bool = True
    """针对openAI, 是否是阿里云百练平台的接口"""

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
            "llm_base_url": "http://192.168.88.1:11434/v1",
            "embedding_base_url": "http://192.168.88.1:11434/v1",
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
            "llm_base_url": "https://api.openai.com/v1",
            "embedding_base_url": "https://api.openai.com/v1",
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


class AlertToolParam(MyBaseModel):
    """工具参数定义"""
    name: str = ""
    """参数名称"""

    type: str = "string"
    """参数类型：string, integer, number, boolean, array, object"""

    description: str = ""
    """参数描述，用于LLM理解参数含义"""

    required: bool = True
    """是否必填"""


class AlertToolConfig(MyBaseModel):
    """告警工具配置"""
    name: str = ""
    """工具名称（函数名）"""

    description: str = ""
    """工具函数的描述文档，用于LLM理解工具用途"""

    params: t.List[AlertToolParam] = []
    """工具输入参数列表"""

    url: str = ""
    """HTTP POST 请求的 URL"""

    method: t.Literal["GET", "POST"] = "POST"
    """请求方法"""

    timeout: int = 30
    """请求超时时间（秒）"""


class AgentToolsSettings(BaseFileSettings):
    """Agent 工具配置 - 支持通过 HTTP 调用外部服务"""

    model_config = SettingsConfigDict(yaml_file=CHATCHAT_ROOT / "agent_tools_settings.yaml")

    ALERT_TOOLS: t.List[AlertToolConfig] = [
        AlertToolConfig(**{
            "name": "get_alert_overview",
            "description": "获取指定时间范围告警总览：总数、等级、状态分布",
            "params": [
                {"name": "start_date", "type": "string", "description": "开始日期，格式YYYY-MM-DD", "required": True},
                {"name": "end_date", "type": "string", "description": "结束日期，格式YYYY-MM-DD", "required": True},
            ],
            "url": "http://127.0.0.1:7862/tools/alert/overview",
            "method": "POST",
            "timeout": 30,
            "headers": {"Content-Type": "application/json"},
        }),
        AlertToolConfig(**{
            "name": "get_alert_trend",
            "description": "获取指定时间范围告警趋势数据，返回每日告警数量变化",
            "params": [
                {"name": "start_date", "type": "string", "description": "开始日期，格式YYYY-MM-DD", "required": True},
                {"name": "end_date", "type": "string", "description": "结束日期，格式YYYY-MM-DD", "required": True},
            ],
            "url": "http://127.0.0.1:7862/tools/alert/trend",
            "method": "POST",
            "timeout": 30,
        }),
        AlertToolConfig(**{
            "name": "get_alert_type_dist",
            "description": "获取指定时间范围告警类型分布统计",
            "params": [
                {"name": "start_date", "type": "string", "description": "开始日期，格式YYYY-MM-DD", "required": True},
                {"name": "end_date", "type": "string", "description": "结束日期，格式YYYY-MM-DD", "required": True},
            ],
            "url": "http://127.0.0.1:7862/tools/alert/type-dist",
            "method": "POST",
            "timeout": 30,
        }),
        AlertToolConfig(**{
            "name": "get_institution_ranking",
            "description": "获取指定时间范围各机构/区域告警数量排行",
            "params": [
                {"name": "start_date", "type": "string", "description": "开始日期，格式YYYY-MM-DD", "required": True},
                {"name": "end_date", "type": "string", "description": "结束日期，格式YYYY-MM-DD", "required": True},
            ],
            "url": "http://127.0.0.1:7862/tools/alert/institution-ranking",
            "method": "POST",
            "timeout": 30,
        }),
    ]
    """告警工具列表，配置各个工具的调用信息"""


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
        "analyze": (
            "你是电力行业告警处置报告审核专家，严格遵循《电力监控系统安全防护规定》《网络安全法》，审核以下报告:\n"
            "【研判维度】\n"
            "1. 内容完整性，包括原因分析、整改结果、设备信息、故障排查过程、是否全面排查"
            "2. 处置合规性：处置步骤是否清晰可追溯，处置结果是否明确\n"
            "3. 原因分析有效性：原因是否明确，内容是否符合逻辑\n"
            "4. 整改闭环：整改措施具体可执行\n"
            "5. 如果严重违规的告警，是否按照四不放过原则进行分析和整改(事故原因未查清不放过、责任人员未处理不放过、整改措施未落实不放过、有关人员未受到教育不放过),"
            "如果没有严格按照四不放过原则进行分析和整改，则直接驳回\n"
            "6. 历史一致性：与同类告警处置方案无矛盾，差异需说明合理原因\n\n"
            "【同类电力告警参考】\n"
            "{{retrieved_info}}\n\n"
            "【本次待审核报告】\n"
            "{{report_info}}\n\n"
            "【输出要求】\n"
            "1. 严格按以下 JSON 输出，禁止多余文字、解释、标点外内容。\n"
            "2. audit_result 只能是：通过 / 驳回 / 需人工复核。\n"
            "3. audit_details：必须详细逐条对照研判维度说明审核情况，写明合规点、问题点、缺失内容，180字左右。\n"
            "4. summary：详细总结本次告警的基本情况、处置过程、存在问题，120字左右。\n"
            "5. reject_reason：驳回时填写具体修改意见，否则为空字符串。\n"
            "6. power_suggestion：给出电力行业针对性优化与防范建议。\n"
            "7. 字段名称、结构、引号必须完全一致。\n\n"
            "【返回JSON结构】"
            "{"
            "'audit_result': '',\n"
            "'audit_details': '',\n"
            "'summary': '',\n"
            "'reject_reason': '',\n"
            "'power_suggestion': ''\n"
            "} "),

        "extract": (
            "你是专业的信息抽取助手。请从下面的【Word识别文本】和【Word识别表格】中，严格按照要求抽取结构化信息，只返回标准JSON。\n"
            "【抽取规则】\n"
            "1. 严格按照指定字段抽取，不要遗漏，不要新增字段。\n"
            "2. 内容必须忠实原文，不编造、不脑补、不扩写。\n"
            "3. 若某个字段无信息，填空字符串 ""。\n"
            "4. 告警是否违规：只能填 '是' 或 '否' 或 ''。\n"
            "5. 判断是否违规依据：事件内容中是否包含违反《电力监控系统安全防护规定》类似字样。\n"
            "6. 时间格式保持原文格式。\n"
            "【Word识别文本】\n"
            "{{full_text}}\n"
            "【Word识别表格数据】\n"
            "{{table_data}}\n\n"
            "【输出要求】严格按以下JSON格式返回，key的字段一定要匹配\n"
            "{"
            "'报告标题': '',"
            "'告警信息': '',"
            "'告警是否违规': '',"
            "'设备名称': '',"
            "'设备类型': '',"
            "'告警时间': '',"
            "'告警内容': '',"
            "'处置过程': '',"
            "'原因分析': '',"
            "'责任人员和责任单位处理': '',"
            "'人员教育培训': '',"
            "'整改情况': '',"
            "'防范措施': ''"
            "}"

        )
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

    agent: dict = {
        "default": "{{input}}",
        "alert_polish": (
            "你是电力监控告警分析专职专员，深耕电力运维、电网监控告警数据分析工作，"
            "负责结合用户提问与原始告警上下文数据，完成专业解读、数据整理、内容润色与问题答复。\n"
            "核心工作要求：\n"
            "1. 精准应答：严格围绕用户提问作答，紧扣告警原始信息，针对性解决问题，不偏离主题。\n"
            "2. 数据完整：完整保留全部数值、时间区间、设备名称、告警类型、频次、点位等关键数据，严禁篡改、遗漏、删减原始信息。\n"
            "3. 排版规范：内容条理清晰，强制分段换行，核心内容采用分点罗列形式展示，层级分明。\n"
            "4. 重点标注：核心指标、异常数据、告警数量、关键时段、故障点位等重要信息使用加粗突出展示。\n"
            "5. 文风专业：贴合电力监控、电网运维工作场景，语气严谨正式、客观中立，语句精简干练，杜绝冗余话术、口语化表达。\n"
            "6. 格式限制：仅输出纯自然文字段落，禁止生成表格、JSON、代码、特殊符号、markdown 复杂格式及无效占位内容。\n"
            "7. 内容优化：对原始杂乱告警数据进行梳理整合、逻辑排序、语句润色，修正语序混乱问题，让数据呈现更易读、专业性更强。\n"
            "执行规则：\n"
            "结合用户问题：{{question}}\n"
            "基于以下告警原始上下文数据：{{alert_context}}\n"
            "整合梳理、规范排版、专业润色后，输出完整分析答复内容。\n"
        ),
        "supervisor": (
            "仅输出一个单词：alert / rag / llm\n"
            "1. 告警、告警统计、电厂、地调、调度、故障 → alert\n"
            "2. 电力监控、电网、电力设备、电力知识 → rag\n"
            "3. 普通闲聊、常识、其他问题 → llm\n"
            "问题：{{question}}\n"
        ),
        "empty": (
            "请你回答我的问题:\n"
            "{{question}}"
        ),
    }
    '''智能体调用模板'''


class SettingsContainer:
    CHATCHAT_ROOT = CHATCHAT_ROOT

    basic_settings: BasicSettings = settings_property(BasicSettings())
    kb_settings: KBSettings = settings_property(KBSettings())
    model_settings: ApiModelSettings = settings_property(ApiModelSettings())
    agent_tools_settings: AgentToolsSettings = settings_property(AgentToolsSettings())
    prompt_settings: PromptSettings = settings_property(PromptSettings())

    def create_all_templates(self):
        self.basic_settings.create_template_file(write_file=True)
        self.kb_settings.create_template_file(write_file=True)
        self.model_settings.create_template_file(sub_comments={
            "MODEL_PLATFORMS": {"model_obj": PlatformConfig(),
                                "is_entire_comment": True}},
            write_file=True)
        self.agent_tools_settings.create_template_file(sub_comments={
            "ALERT_TOOLS": {"model_obj": AlertToolConfig(),
                            "is_entire_comment": True}},
            write_file=True)
        self.prompt_settings.create_template_file(write_file=True, file_format="yaml")

    def set_auto_reload(self, flag: bool = True):
        self.basic_settings.auto_reload = flag
        self.kb_settings.auto_reload = flag
        self.model_settings.auto_reload = flag
        self.agent_tools_settings.auto_reload = flag
        self.prompt_settings.auto_reload = flag


Settings = SettingsContainer()

if __name__ == "__main__":
    Settings.create_all_templates()
