from typing import Dict, List, Literal, NamedTuple, Optional
from pydantic import BaseModel, Field, field_validator

# ====================== 输入/输出模型 ======================

class IssueItem(BaseModel):
    """单个问题明细（字段均为字符串）"""
    content: str = Field(..., description="问题描述原文")
    securityType: str = Field(default="", description="安全类型（字符串，如：安全计算环境）")
    riskLevel: str = Field(default="", description="风险级别（字符串，如：中）")

    @field_validator("content", "securityType", "riskLevel", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        # 容错：传入的非字符串标量统一转为字符串
        if v is None:
            return ""
        return v if isinstance(v, str) else str(v)


class YearlyIssues(BaseModel):
    """某个年份对应的一堆问题"""
    year: str = Field(..., description="年份，例如 2026")
    issues: List[IssueItem] = Field(..., description="该年份的问题明细列表")

    @field_validator("year", mode="before")
    @classmethod
    def _coerce_year(cls, v):
        # 年份允许传 int（如 2026），统一转成字符串
        return "" if v is None else str(v).strip()


class DuplicateDetectRequest(BaseModel):
    """重复问题检测请求"""
    items: List[YearlyIssues] = Field(
        ...,
        description="按年份组织的问题明细：2026年对应一堆问题，2027年对应一堆问题",
    )
    method: Literal["keyword", "edit_distance", "ngram", "combo"] = Field(
        default="keyword",
        description=(
            "相似度计算方法："
            "keyword=jieba分词+词集合Jaccard（关键词重合度，默认）；"
            "edit_distance=字符级Levenshtein编辑距离归一化（字面改写）；"
            "ngram=字符n-gram余弦（局部字序鲁棒）；"
            "combo=多方法加权融合"
        ),
    )
    threshold: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="相似度阈值，任意一对相似度 >= 阈值即判定为同一问题；None 时使用该方法默认阈值"
                    "（keyword 0.60 / edit_distance 0.75 / ngram 0.70 / combo 0.70），可用少量标注样本调参",
    )
    methodWeights: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "combo 融合权重（仅 method=combo 时生效），如 "
            '{"keyword": 0.4, "edit_distance": 0.3, "ngram": 0.3}；'
            "不传使用默认权重"
        ),
    )
    includeSingletons: bool = Field(default=False, description="是否输出仅出现一次（无重复）的问题簇")
    crossYearOnly: bool = Field(
        default=True,
        description=(
            "是否启用跨年份约束（默认 True）：同一个聚类内不允许出现同一年份的两条问题，"
            "只有不同年份的问题才可能被合并到同一个聚类中"
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "year": "2026",
                        "issues": [
                            {"content": "未对登录的用户进行身份标识唯一性检查", "securityType": "安全计算环境", "riskLevel": "中"},
                        ],
                    },
                    {
                        "year": "2027",
                        "issues": [
                            {"content": "未对登录的用户进行身份标识唯一性检查", "securityType": "安全计算环境", "riskLevel": "中"},
                        ],
                    },
                ],
                "method": "keyword",
                "threshold": 0.60,
            }
        }


class ClusterOccurrence(BaseModel):
    """簇内单条明细：年份 + 原文"""
    year: str = Field(..., description="年份")
    content: str = Field(..., description="问题描述原文")


class DuplicateCluster(BaseModel):
    """重复问题簇：同一个根源重复问题"""
    clusterId: int = Field(..., description="簇编号（按出现次数降序编排）")
    securityType: str = Field(..., description="安全类型（输入字符串）")
    riskLevel: str = Field(..., description="风险级别（输入字符串）")
    count: int = Field(..., description="该重复问题出现的次数（簇大小）")
    years: List[str] = Field(..., description="出现过的年份列表（升序去重）")
    representativeContent: str = Field(..., description="簇内与其他成员平均相似度最高的一条，视为根源问题的最佳表述")
    occurrences: List[ClusterOccurrence] = Field(..., description="簇内每一条明细（年份、原文）")


class DuplicateDetectResponse(BaseModel):
    """重复问题检测结果"""
    threshold: float = Field(..., description="本次检测使用的相似度阈值")
    method: str = Field(..., description="本次使用的相似度计算方法")
    totalItems: int = Field(..., description="参与检测的问题条数")
    groupCount: int = Field(..., description="比对分组数量（按安全类型+风险级别划分）")
    duplicateClusterCount: int = Field(..., description="重复问题簇数量（出现次数 >= 2）")
    duplicateItemCount: int = Field(..., description="涉及重复的问题条数")
    clusters: List[DuplicateCluster] = Field(..., description="重复问题簇列表，按出现次数降序")




class FlatIssue(NamedTuple):
    """内部展平后的问题记录：年份 + 问题明细"""
    year: str
    content: str
    security_type: str
    risk_level: str