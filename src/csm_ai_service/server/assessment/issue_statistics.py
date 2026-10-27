"""
监测评估模块 —— 重复问题检测的统计口径

统计口径说明：
1. 统计窗口由请求的 startYear ~ endYear 决定（含首尾），逐年输出；
2. 重复问题 = 该年出现、且上一年度也出现过（同一簇内相邻两年都有成员）：
   - 若上一年度数据未传入（例如窗口起点是 2024、但没有传 2023 的数据），
     该年的重复问题数按 0 计算，重复问题的风险分布也全为 0；
3. 重复问题总览：重复簇个数；已整改/未整改、高/中/低风险分布、安全类型分布
   均以"簇内最后一个年份的信息"（DuplicateCluster.rectified / riskLevel）为准。

年份口径：全流程统一使用 int（FlatIssue.year / ClusterOccurrence.year / 统计输出均为 int）。
"""
from collections import Counter
from typing import Dict, List, Optional, Tuple

from csm_ai_service.server.assessment.api_scheme import (
    CountItem,
    DuplicateCluster,
    DuplicateOverview,
    FlatIssue,
    RiskDistribution,
    YearlyDuplicateStats,
    YearlyRectification, ClusterOccurrence,
)

# 风险级别的标准三段分类（其余取值不计入高/中/低）
RISK_HIGH = "高风险"
RISK_MEDIUM = "中风险"
RISK_LOW = "低风险"

HIGH_TOKENS = {"高风险", "高", "high", "严重", "重大", "紧急"}
MEDIUM_TOKENS = {"中风险", "中", "medium", "mediumrisk", "一般", "中等"}
LOW_TOKENS = {"低风险", "低", "low", "轻微", "低危"}


# ====================== 基础工具 ======================

def normalize_risk(risk_level: str) -> Optional[str]:
    """把风险级别归一化到 高风险 / 中风险 / 低风险；无法识别返回 None"""
    text = (risk_level or "").strip()
    if not text:
        return None
    lowered = text.lower().replace(" ", "")
    if lowered in HIGH_TOKENS or "高" in text:
        return RISK_HIGH
    if lowered in MEDIUM_TOKENS or "中" in text:
        return RISK_MEDIUM
    if lowered in LOW_TOKENS or "低" in text:
        return RISK_LOW
    return None


def collect_year_items(flat_items: List[FlatIssue]) -> Dict[int, List[FlatIssue]]:
    """按年份归类展平后的问题，年份升序返回"""
    by_year: Dict[int, List[FlatIssue]] = {}
    for item in flat_items:
        by_year.setdefault(item.year, []).append(item)
    return {year: by_year[year] for year in sorted(by_year)}


def _distribution(values: List[str]) -> List[CountItem]:
    """按名称分组计数，按数量降序（同数量按名称升序保证稳定）"""
    counter = Counter(value or "未知" for value in values)
    return [
        CountItem(name=name, count=count)
        for name, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _risk_distribution(risk_levels: List[str]) -> RiskDistribution:
    """统计高/中/低风险条数（固定三段，无法识别的风险级别不计入）"""
    counter = Counter(filter(None, (normalize_risk(level) for level in risk_levels)))
    return RiskDistribution(
        high=counter.get(RISK_HIGH, 0),
        medium=counter.get(RISK_MEDIUM, 0),
        low=counter.get(RISK_LOW, 0),
    )


def resolve_report_years(start_year: int, end_year: int) -> List[int]:
    """解析统计窗口年份（含首尾，年份升序）；结束年份小于开始年份时自动交换"""
    if end_year < start_year:
        start_year, end_year = end_year, start_year
    return list(range(start_year, end_year + 1))


# ====================== 1. 重复问题总览 ======================

def build_duplicate_overview(duplicate_clusters: List[DuplicateCluster]) -> DuplicateOverview:
    """
    重复问题总览统计（整改、风险、安全类型均按簇内最后一个年份的信息统计）。
    """
    return DuplicateOverview(
        duplicateClusterCount=len(duplicate_clusters),
        rectifiedCount=sum(1 for c in duplicate_clusters if c.rectified),
        unrectifiedCount=sum(1 for c in duplicate_clusters if not c.rectified),
        riskDistribution=_risk_distribution([c.riskLevel for c in duplicate_clusters]),
        securityTypeDistribution=_distribution([c.securityType for c in duplicate_clusters]),
    )


# ====================== 2. 历年重复问题明细 ======================

def _occurrence_of(cluster: DuplicateCluster, year: int) -> Optional[ClusterOccurrence]:
    """取簇内指定年份的第一条明细；不存在返回 None"""
    for occ in cluster.occurrences:
        if occ.year == year:
            return occ
    return None


def collect_duplicate_occurrences(
        duplicate_clusters: List[DuplicateCluster],
        year: int,
        prev_year: Optional[int],
) -> List[ClusterOccurrence]:
    """
    收集某年份的重复问题（今年与上一年度在同一簇中都有成员）。
    prev_year 为 None（上年数据未传入）时返回空列表，即该年重复问题按 0 统计。
    """
    if prev_year is None:
        return []
    result = []
    for cluster in duplicate_clusters:
        current = _occurrence_of(cluster, year)
        if current is None or _occurrence_of(cluster, prev_year) is None:
            continue
        result.append(current)
    return result


# ====================== 3. 历年整改统计 ======================

def build_yearly_rectification(
        year_items: Dict[int, List[FlatIssue]],
        duplicate_clusters: List[DuplicateCluster],
        report_years: List[int],
) -> List[YearlyRectification]:
    """
    历年问题整改情况（按年份升序，覆盖统计窗口内的每一年）。

    :param year_items: 已传入年份的问题（可能包含窗口外的基准年）
    :param duplicate_clusters: 重复簇
    :param report_years: 统计窗口年份
    """
    result: List[YearlyRectification] = []
    for year in report_years:
        items = year_items.get(year, [])
        # 上年数据未传入时，重复问题按 0 统计
        prev_year = year - 1 if (year - 1) in year_items else None
        duplicates = collect_duplicate_occurrences(duplicate_clusters, year, prev_year)
        rectified = sum(1 for it in items if it.rectified)
        result.append(YearlyRectification(
            year=year,
            previousYear=prev_year,
            total=len(items),
            rectifiedCount=rectified,
            unrectifiedCount=len(items) - rectified,
            duplicateCount=len(duplicates),
        ))
    return result


# ====================== 4. 历年重复问题及风险分布 ======================

def build_yearly_duplicates(
        year_items: Dict[int, List[FlatIssue]],
        duplicate_clusters: List[DuplicateCluster],
        report_years: List[int],
) -> List[YearlyDuplicateStats]:
    """历年重复问题及风险分布（按年份升序，覆盖统计窗口内的每一年）"""
    result: List[YearlyDuplicateStats] = []
    for year in report_years:
        prev_year = year - 1 if (year - 1) in year_items else None
        current_year_items = collect_duplicate_occurrences(duplicate_clusters, year, prev_year)
        result.append(YearlyDuplicateStats(
            year=year,
            previousYear=prev_year,
            total=len(year_items.get(year, [])),
            duplicateCount=len(current_year_items),
            riskDistribution=_risk_distribution([occ.riskLevel for occ in current_year_items]),
        ))
    return result
