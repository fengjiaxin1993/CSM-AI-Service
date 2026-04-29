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
    
    default: t.Any = None
    """默认值"""


class AlertToolConfig(MyBaseModel):
    """告警工具配置"""
    name: str = ""
    """工具名称（函数名）"""
    
    description: str = ""
    """工具函数的描述文档，用于LLM理解工具用途"""
    
    params: t.List[AlertToolParam] = []
    """工具输入参数列表"""
    
    return_schema: t.Dict[str, t.Any] = {}
    """返回数据格式定义，用于LLM理解工具返回的数据结构"""
    
    return_description: str = ""
    """返回数据描述，说明返回值的格式和内容"""
    
    url: str = ""
    """HTTP POST 请求的 URL"""
    
    method: t.Literal["GET", "POST"] = "POST"
    """请求方法"""
    
    timeout: int = 30
    """请求超时时间（秒）"""
    
    headers: t.Dict[str, str] = {}
    """请求头"""


class AgentToolsSettings(BaseFileSettings):
    """Agent 工具配置 - 支持通过 HTTP 调用外部服务"""
    
    model_config = SettingsConfigDict(yaml_file=CHATCHAT_ROOT / "agent_tools_settings.yaml")
    
    ALERT_API_BASE_URL: str = ""
    """告警 API 基础 URL，如果配置则优先使用 HTTP 调用"""
    
    ALERT_TOOLS: t.List[AlertToolConfig] = [
        AlertToolConfig(**{
            "name": "get_alert_overview",
            "description": "获取指定时间范围告警总览：总数、等级、状态分布",
            "params": [
                {"name": "start_date", "type": "string", "description": "开始日期，格式YYYY-MM-DD", "required": True},
                {"name": "end_date", "type": "string", "description": "结束日期，格式YYYY-MM-DD", "required": True},
            ],
            "return_schema": {
                "时间范围": "string",
                "告警总数": "integer",
                "紧急告警数": "integer",
                "重要告警数": "integer",
                "待处置数量": "integer",
                "已归档数量": "integer",
            },
            "return_description": "返回JSON格式的告警统计数据，包含时间范围、告警总数、各等级告警数量等",
            "url": "/api/alert/overview",
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
            "return_schema": {
                "时间范围": "string",
                "每日趋势": [{"日期": "integer"}],
            },
            "return_description": "返回JSON格式的趋势数据，包含时间范围和每日告警数量列表",
            "url": "/api/alert/trend",
            "method": "POST",
            "timeout": 30,
            "headers": {"Content-Type": "application/json"},
        }),
        AlertToolConfig(**{
            "name": "get_alert_type_dist",
            "description": "获取指定时间范围告警类型分布统计",
            "params": [
                {"name": "start_date", "type": "string", "description": "开始日期，格式YYYY-MM-DD", "required": True},
                {"name": "end_date", "type": "string", "description": "结束日期，格式YYYY-MM-DD", "required": True},
            ],
            "return_schema": {
                "时间范围": "string",
                "告警类型统计": {"类型名称": "integer"},
            },
            "return_description": "返回JSON格式的告警类型分布，包含各类型的数量统计",
            "url": "/api/alert/type-distribution",
            "method": "POST",
            "timeout": 30,
            "headers": {"Content-Type": "application/json"},
        }),
        AlertToolConfig(**{
            "name": "get_institution_ranking",
            "description": "获取指定时间范围各机构/区域告警数量排行",
            "params": [
                {"name": "start_date", "type": "string", "description": "开始日期，格式YYYY-MM-DD", "required": True},
                {"name": "end_date", "type": "string", "description": "结束日期，格式YYYY-MM-DD", "required": True},
            ],
            "return_schema": {
                "时间范围": "string",
                "区域告警排行": [{"机构名称": "integer"}],
            },
            "return_description": "返回JSON格式的机构排行数据，按告警数量降序排列",
            "url": "/api/alert/institution-ranking",
            "method": "POST",
            "timeout": 30,
            "headers": {"Content-Type": "application/json"},
        }),
    ]
    """告警工具列表，配置各个工具的调用信息"""
    
    USE_MOCK_DATA: bool = True
    """是否使用模拟数据（当 HTTP 调用失败或配置为空时使用）"""


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
        "time_parse": (
            "你是时间类型识别器，**只输出一个英文关键词**，不要任何其他内容：\n"
            "可选关键词：\n"
            "today      → 今天\n"
            "yesterday  → 昨天\n"
            "last7d     → 近7天\n"
            "last30d    → 近30天\n"
            "thisMonth  → 本月\n"
            "lastMonth  → 上月\n"
            "thisYear   → 今年\n"
            "unknown    → 无法识别\n"
            "识别时间类型：{{question}}\n"
        ),
        "alert_polish": (
            "你是电力监控告警分析专员，处理告警统计数据。\n"
            "要求：\n"
            "1. 内容条理清晰，**必须分段换行**，关键信息分点；\n"
            "2. 完整保留所有数值、时间范围、关键数据，不得删减；\n"
            "3. 语气专业严谨，贴合电力监控运维场景；\n"
            "4. 避免冗余废话，语句简洁；\n"
            "5. 关键数据可用加粗强调（纯文本换行即可）；\n"
            "6. 禁止输出JSON、代码、表格，全部转为自然段落。\n"
        
            "请整理并润色以下告警统计数据，排版分段展示：\n"
            "{{question}}\n"
        ),
        "supervisor": (
            "仅输出一个单词：alert / rag / llm\n"
            "1. 告警、告警统计、电厂、地调、调度、故障 → alert\n"
            "2. 电力监控、电网、电力设备、电力知识 → rag\n"
            "3. 普通闲聊、常识、其他问题 → llm\n"      
            "问题：{{question}}\n"
        ),
        "file_related": (
            "请判断以下用户提问是否需要对文档进行操作。\n"
            "用户提问: {question}\n"
            "请只回答 YES 或 NO:\n"
                "- YES: 需要针对文档进行操作（总结、概括、提取、解读、分析、对比文档内容等）\n"
                "- NO: 无文档操作需求的所有问题\n"
            "回答:\n"
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
