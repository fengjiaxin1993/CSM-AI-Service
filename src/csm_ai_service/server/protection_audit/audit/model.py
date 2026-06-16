from typing import List

from pydantic import BaseModel

# ====================== 数据模型 ======================
class AuditRule(BaseModel):
    id: int  # 规则唯一ID
    name: str  # 规则名称（简短描述）
    description: str  # 规则详细描述（用于提示大模型）
    chapter_keywords: List[str]
    judge_logic: str  # 判断逻辑


class RuleAuditResult(BaseModel):
    contract_id: int  # 合同ID
    rule_id: int  # 规则ID
    rule_name: str  # 规则名称
    rule_description: str  # 规则详细描述（用于提示大模型）
    rule_judge_logic: str  # 判断逻辑
    related_chapters: List[str]  # 引用的相关章节名
    related_text: str  # 引用的相关原文
    related_doc_ids: List[str]  # 引用的相关文档ID
    is_compliant: bool  # 是否合规
    conclusion: str  # 结论描述
    reasoning: str  # 判断理由/解释
    origin_text: str  # 从原文中找出相关的内容
