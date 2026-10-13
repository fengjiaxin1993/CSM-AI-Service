from string import Template
from typing import Dict

from csm_ai_service.server.csm_analyze.warning_analysis.extract_info.helper import output_standard_dict
from csm_ai_service.server.utils import get_ChatOpenAI, get_default_llm, fix_llm_json_output

### 提取json信息

def init_report_json_data() -> Dict:
    """初始化报告结构化字段（中文键）"""
    return {
        "报告标题": "",
        "告警信息": "",
        "设备名称": "",
        "设备类型": "",
        "告警时间": "",
        "告警内容": "",
        "处置过程": "",
        "原因分析": "",
        "责任人员和责任单位处理": "",
        "人员教育培训": "",
        "整改情况": "",
        "佐证材料": "",
    }


# 提示词模板，占位符使用 ${markdown_content}
extract_prompt_template = Template("""
你是专业信息抽取助手，请从下方【Markdown正文】中严格按照规则抽取结构化信息，仅返回标准JSON，禁止输出额外解释、说明文本。

【抽取规则】
1. 严格使用指定字段抽取，不得遗漏字段、不得新增自定义字段。
2. 抽取内容完全忠实Markdown原文，禁止编造、脑补、扩写、改写语义。
3. 字段无对应信息时，填空字符串 ""。
4. 告警是否违规：仅允许填写 '是' / '否' / ''；判断依据：事件内容是否出现违反《电力监控系统安全防护规定》相关字样。
5. 时间直接保留原文格式，不做格式转换。

【Markdown正文】
${markdown_content}

【输出固定JSON结构，key必须完全匹配，顺序保持一致】
{
    "报告标题": "",
    "告警信息": "",
    "设备名称": "",
    "设备类型": "",
    "告警时间": "",
    "告警内容": "",
    "处置过程": "",
    "原因分析": "",
    "责任人员和责任单位处理": "",
    "人员教育培训": "",
    "整改情况": "",
    "佐证材料": "",
}
""")


def build_extract_prompt(markdown_content: str) -> str:
    """构造完整提示词，传入markdown文本，返回组装完成prompt字符串"""
    return extract_prompt_template.substitute(markdown_content=markdown_content)



def extract_json_from_markdown(markdown_content: str) -> Dict:
    """
    调用大模型从Word文档中提取结构化数据

    Args:
        markdown_content: Word文档的段落文本内容

    Returns:
        解析后的结构化数据字典
    """

    model = get_default_llm()
    llm = get_ChatOpenAI(
        model_name=model,
        temperature=0.1,
        max_tokens=len(markdown_content) + 1024,
    )

    # 构建提示词
    prompt = build_extract_prompt(markdown_content)
    response = llm.invoke(prompt)  # 一次性调用模型，返回完整响应
    content = str(response.content)  # 核心：提取完整回答文本
    fix_dic = fix_llm_json_output(content)
    return output_standard_dict(init_report_json_data(), fix_dic)


