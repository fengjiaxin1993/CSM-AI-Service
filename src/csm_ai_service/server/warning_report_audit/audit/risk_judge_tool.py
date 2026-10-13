from string import Template
from csm_ai_service.server.utils import get_ChatOpenAI, get_default_llm, fix_llm_json_output
from csm_ai_service.utils import build_logger
logger = build_logger()

### 风险等级判断


# 提示词模板，占位符使用 ${markdown_content}
risk_judge_prompt_template = Template("""
你是电力监控系统告警分级专家。请根据以下告警内容，判断该告警是否属于高危告警。

高危告警的特征包括：
1. 445端口相关告警（如端口扫描、端口爆破、SMB漏洞利用等）
2. 违规外联/非法外联（内网设备未经授权连接外部网络）
3. 3389端口相关告警（如远程桌面暴力破解、RDP漏洞利用等）
4. 病毒/木马/恶意程序/恶意代码/勒索/挖矿/后门等恶意软件告警
5. 互联网地址访问（内网设备访问互联网地址）

普通告警的特征：
- 一般性的端口告警（非445/3389等高危端口）
- 常规的设备状态告警
- 低风险的网络行为告警
- 不涉及安全威胁的运维类告警

【告警内容】
${alert_content}

请严格按以下JSON格式输出，不要输出其他任何内容：
{{"is_high_risk": true或false, "reason": "简要说明判断理由"}}
""")


def build_judge_prompt(alert_content: str) -> str:
    """构造完整提示词，传入markdown文本，返回组装完成prompt字符串"""
    return risk_judge_prompt_template.substitute(alert_content=alert_content)


def is_high_risk_alert(alert_content: str) -> bool:
    """通过大模型判断告警是否为高危告警，返回True/False"""
    if not alert_content:
        return False
    try:
        llm = get_ChatOpenAI(
            model_name=get_default_llm(),
            temperature=0.1,
            max_tokens=200,
        )
        # 构建提示词
        prompt = build_judge_prompt(alert_content)
        response = llm.invoke(prompt)
        result = fix_llm_json_output(str(response.content))
        is_high = result.get("is_high_risk", False)
        reason = result.get("reason", "")
        logger.info(f"大模型判断高危告警结果：is_high_risk={is_high}，理由：{reason}")
        return bool(is_high)
    except Exception as e:
        logger.warning(f"大模型判断高危告警失败，降级为普通告警: {e}")
        return False
