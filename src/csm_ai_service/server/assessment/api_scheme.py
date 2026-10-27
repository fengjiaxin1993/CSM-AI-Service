from typing import List, NamedTuple, Optional
from pydantic import BaseModel, Field, field_validator

from csm_ai_service.server.assessment.text_similarity import DEFAULT_THRESHOLD


# ====================== 输入/输出模型 ======================

def _coerce_bool(v) -> bool:
    """已整改"/"未整改"""
    if v is None:
        return False
    text = str(v).strip().lower()
    return text == "已整改"



class IssueItem(BaseModel):
    """单个问题明细（字符串字段 + 整改状态）"""
    content: str = Field(..., description="问题描述原文")
    securityType: str = Field(default="", description="安全类型（字符串，如：安全计算环境）")
    riskLevel: str = Field(default="", description="风险级别（字符串，如：中/高风险）")
    rectified: bool = Field(default=False, description="是否已整改（True=已整改 / False=未整改）")

    @field_validator("rectified", mode="before")
    @classmethod
    def _coerce_rectified(cls, v):
        return _coerce_bool(v)



class YearlyIssues(BaseModel):
    """某个年份对应的一堆问题"""
    year: int = Field(..., description="年份（int），例如 2026")
    issues: List[IssueItem] = Field(..., description="该年份的问题明细列表")


class DuplicateDetectRequest(BaseModel):
    """重复问题检测请求（相似度固定使用 keyword 关键词法）"""

    startYear: int = Field(
        ...,
        description="统计开始年份（含），如 2024；用于同比的 2023 年数据若未传入，则该年重复问题按 0 统计",
    )
    endYear: int = Field(
        ...,
        description="统计结束年份（含），如 2024；取值需大于等于 startYear",
    )
    items: List[YearlyIssues] = Field(
        ...,
        description="按年份组织的问题明细：2026年对应一堆问题，2027年对应一堆问题",
    )
    threshold: float = Field(
        default=DEFAULT_THRESHOLD,
        ge=0.0, le=1.0,
        description="相似度阈值（keyword 词集合 Jaccard）：相似度 >= 阈值才允许归入同一簇；"
                    "None 时使用默认阈值 0.60，可用少量标注样本调参",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "startYear": 2026,
                "endYear": 2027,
                "threshold": 0.60,
                "items": [
                    {
                        "year": 2026,
                        "issues": [
                            {"content": "未对登录的用户进行身份标识唯一性检查", "securityType": "安全计算环境",
                             "riskLevel": "中风险", "rectified": True},
                        ],
                    },
                    {
                        "year": 2027,
                        "issues": [
                            {"content": "未对登录的用户进行身份标识唯一性检查", "securityType": "安全计算环境",
                             "riskLevel": "高风险", "rectified": False},
                        ],
                    },
                ]
            }
        }


# ====================== 输出：簇与明细 ======================

class ClusterOccurrence(BaseModel):
    """簇内单条明细：年份 + 原文 + 风险 + 整改状态"""
    year: int = Field(..., description="年份")
    content: str = Field(..., description="问题描述原文")
    riskLevel: str = Field(default="", description="该条问题的风险级别（如：高风险）")
    rectified: bool = Field(..., description="该条问题是否已整改")


class DuplicateCluster(BaseModel):
    """重复问题簇：同一个根源重复问题（同一安全类型、相邻年份串联而成）"""
    clusterId: int = Field(..., description="簇编号（按出现次数降序编排）")
    securityType: str = Field(..., description="安全类型（簇内问题均属同一安全类型）")
    count: int = Field(..., description="该重复问题出现的次数（簇大小）")
    years: List[int] = Field(..., description="出现过的年份列表（升序去重）")
    riskLevel: str = Field(..., description="风险级别，取簇内最后一个年份的信息")
    rectified: bool = Field(..., description="是否已整改，取簇内最后一个年份的信息")
    content: str = Field(..., description="问题描述原文，取簇内最后一个年份的信息")
    occurrences: List[ClusterOccurrence] = Field(..., description="簇内每一条明细（年份、原文、风险、整改状态）")


# ====================== 输出：统计模型 ======================

class CountItem(BaseModel):
    """通用计数项"""
    name: str = Field(..., description="名称（如 风险级别 / 安全类型 的取值）")
    count: int = Field(..., description="问题/簇数量")


class RiskDistribution(BaseModel):
    """风险类型分布（高/中/低固定三段，便于前端直接取用）"""
    high: int = Field(default=0, description="高风险条数")
    medium: int = Field(default=0, description="中风险条数")
    low: int = Field(default=0, description="低风险条数")


class RectificationStats(BaseModel):
    """整改情况统计"""
    total: int = Field(..., description="总问题条数")
    rectifiedCount: int = Field(..., description="已整改问题条数")
    unrectifiedCount: int = Field(..., description="未整改问题条数")


class DuplicateOverview(BaseModel):
    """重复问题总览统计（整改/风险/安全类型均按簇内最后一个年份的信息统计）"""
    duplicateClusterCount: int = Field(..., description="重复问题簇个数（出现次数 >= 2）")
    rectifiedCount: int = Field(..., description="已整改的重复簇个数（按最后一个年份）")
    unrectifiedCount: int = Field(..., description="未整改的重复簇个数（按最后一个年份）")
    riskDistribution: RiskDistribution = Field(..., description="重复簇的风险类型分布（按最后一个年份）")
    securityTypeDistribution: List[CountItem] = Field(..., description="重复簇的安全类型分布")


class YearlyRectification(BaseModel):
    """某一年度的整改情况（不含同比基准年的年份）"""
    year: int = Field(..., description="年份")
    previousYear: Optional[int] = Field(default=None, description="上一年份（比对基准）")
    total: int = Field(..., description="该年问题总条数")
    rectifiedCount: int = Field(..., description="该年已整改问题条数")
    unrectifiedCount: int = Field(..., description="该年未整改问题条数")
    duplicateCount: int = Field(..., description="该年重复问题数量（上一年度也出现过）")


class DuplicateRecord(BaseModel):
    """重复问题明细：某年中"上一年度也出现过"的问题"""
    clusterId: int = Field(..., description="所属重复问题簇编号")
    year: int = Field(..., description="本年度")
    previousYear: int = Field(..., description="上一年度（比对基准）")
    securityType: str = Field(..., description="安全类型")
    riskLevel: str = Field(..., description="本年度风险级别")
    content: str = Field(..., description="本年度问题原文")
    rectified: bool = Field(..., description="本年度该问题是否已整改")
    previousRiskLevel: str = Field(default="", description="上一年度风险级别")
    previousContent: str = Field(default="", description="上一年度对应问题原文")


class YearlyDuplicateStats(BaseModel):
    """某一年度的重复问题及风险分布"""
    year: int = Field(..., description="年份")
    previousYear: Optional[int] = Field(default=None, description="上一年份（比对基准）")
    total: int = Field(..., description="该年问题总条数")
    duplicateCount: int = Field(..., description="该年重复问题条数（上一年度也出现过）")
    riskDistribution: RiskDistribution = Field(..., description="该年重复问题的风险分布（高/中/低）")


class DuplicateDetectResponse(BaseModel):
    """重复问题检测结果"""
    threshold: float = Field(..., description="本次检测使用的相似度阈值")
    totalItems: int = Field(..., description="参与检测的问题条数")
    duplicateClusterCount: int = Field(..., description="重复问题簇个数（出现次数 >= 2）")
    duplicateItemCount: int = Field(..., description="涉及重复的问题条数")
    clusters: List[DuplicateCluster] = Field(..., description="重复问题簇列表（含明细），按出现次数降序")
    overview: DuplicateOverview = Field(..., description="重复问题总览统计（数量、整改、风险分布、安全类型分布）")
    yearlyRectification: List[YearlyRectification] = Field(..., description="历年问题整改情况（按年份升序，不含基准年）")
    yearlyDuplicates: List[YearlyDuplicateStats] = Field(..., description="历年重复问题及风险分布（按年份升序，不含基准年）")


class FlatIssue(NamedTuple):
    """内部展平后的问题记录：年份 + 问题明细"""
    year: int
    content: str
    security_type: str
    risk_level: str
    rectified: bool = False
