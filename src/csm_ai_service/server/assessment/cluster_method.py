# ====================== 聚类算法 ======================
"""
问题聚类：把历年相似的问题归成一个个"簇"（一个簇 = 同一个根源问题）。

整体思路只有两步：
1. 先按【安全类型】分类：不同安全类型的问题互不比较；
2. 在同一安全类型内部做聚类：按年份从早到晚逐条处理，
   每条问题要么挂到已存在的簇里，要么自己开一个新簇。
   硬性约束：同一年份的问题不能进入同一个簇。

比较相似度时，只与簇内【最后一个年份】的成员比较（不看更早的成员，
因为簇内按年份递进串联，最新一年的表述才代表现状），
用"关键词词集合的 Jaccard 值"（见 text_similarity.py），相似度 >= 阈值 才算同一个问题。

代码里用两个小的数据类代替裸下标：
- IssueNode：一条问题及其预分词结果（只分词一次）；
- ProblemCluster：一个簇及其成员，并提供"今年能不能收这条问题""相似度多少"等方法。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from csm_ai_service.server.assessment.api_scheme import YearlyIssues, FlatIssue, DuplicateDetectResponse, \
    DuplicateCluster, ClusterOccurrence
from csm_ai_service.server.assessment.issue_statistics import (
    build_duplicate_overview,
    build_yearly_duplicates,
    build_yearly_rectification,
    collect_year_items,
    resolve_report_years,
)
from csm_ai_service.server.assessment.text_similarity import (
    EncodedText,
    TextEncoder,
    encode_similarity, DEFAULT_THRESHOLD,
)


# ====================== 数据结构 ======================

@dataclass
class IssueNode:
    """一条问题：原始信息 + 预计算结果（分词只做一次）"""
    content: str
    security_type: str
    risk_level: str
    rectified: bool
    encoded: EncodedText       # 归一化后的文本 + 关键词集合
    year: int                  # 年份（int）


@dataclass
class ProblemCluster:
    """一个簇：同一根源问题的历年记录，成员按年份升序"""
    security_type: str
    members: List[IssueNode] = field(default_factory=list)
    # 已收录的年份（增量维护，避免每次判断都重建集合）
    occupied_years: Set[int] = field(default_factory=set)

    def accepts(self, issue: IssueNode) -> bool:
        """该簇能否接收这条问题：同一年份最多一条（同年互斥）"""
        return issue.year not in self.occupied_years

    def latest(self) -> Optional[IssueNode]:
        """簇内最后一个年份的成员（成员按年份升序，即最后一条）；空簇返回 None"""
        return self.members[-1] if self.members else None

    def similarity_with(self, issue: IssueNode) -> float:
        """
        这条问题与该簇的相似度：只与簇内最后一个年份的成员比较。

        只比最新成员是有意为之：同一簇内年份是逐级串联的，
        与今年的问题是否重复，取决于今年与"最近一次出现"的表述是否接近。
        相似度计算本身统一由 text_similarity.encode_similarity 提供。
        """
        latest = self.latest()
        if latest is None:
            return 0.0
        return encode_similarity(latest.encoded, issue.encoded)

    def add(self, issue: IssueNode) -> None:
        """把问题加入该簇；成员按年份升序，因此新问题一定是最后一条"""
        self.members.append(issue)
        self.occupied_years.add(issue.year)


def create_cluster(issue: IssueNode) -> ProblemCluster:
    """以一条问题为起点新建簇"""
    return ProblemCluster(
        security_type=issue.security_type,
        members=[issue],
        occupied_years={issue.year},
    )


# ====================== 输入整理 ======================

def flatten_yearly_items(yearly_items: List[YearlyIssues]) -> List[FlatIssue]:
    """把"按年份组织的问题"展平成一维列表，跳过空问题描述"""
    flat: List[FlatIssue] = []
    for yearly in yearly_items:
        for item in yearly.issues:
            if (item.content or "").strip():
                flat.append(FlatIssue(
                    year=yearly.year,
                    content=item.content,
                    security_type=item.securityType,
                    risk_level=item.riskLevel,
                    rectified=item.rectified,
                ))
            else:
                print(f"跳过空问题描述: year={yearly.year}")
    return flat


def build_issue_nodes(flat_items: List[FlatIssue]) -> List[IssueNode]:
    """
    展平后的问题 -> IssueNode（每条只分词一次）。
    相同文案只分词一次，重复出现的问题直接复用缓存结果。
    """
    encoder = TextEncoder()
    return [
        IssueNode(
            year=item.year,
            content=item.content,
            security_type=item.security_type,
            risk_level=item.risk_level,
            rectified=item.rectified,
            encoded=encoder.encode(item.content),
        )
        for item in flat_items
    ]


def group_by_security_type(issues: List[IssueNode]) -> Dict[str, List[IssueNode]]:
    """
    步骤 1：按安全类型分类（风险级别不参与分类，只用于统计）。
    返回 {安全类型: [该类型下的问题]}；每类内部按年份升序排列。
    """
    groups: Dict[str, List[IssueNode]] = {}
    for issue in issues:
        groups.setdefault(issue.security_type, []).append(issue)
    for group in groups.values():
        group.sort(key=lambda issue: issue.year)
    return groups


# ====================== 步骤 2：聚类 ======================

def cluster_issues(issues: List[IssueNode], threshold: float) -> List[ProblemCluster]:
    """
    对同一安全类型下的问题聚类（入参已按年份升序）。

    逐条处理，每条问题的处理逻辑：
    1. 在已有簇中，找出"今年还没有成员"且"相似度 >= 阈值"的簇
       （相似度只与簇内最后年份的成员比较）；
    2. 有多个可选时，选相似度最高的那个；
    3. 一个都找不到，就自己开一个新簇。

    :param issues: 同一安全类型的问题，按年份升序
    :param threshold: 相似度阈值（>= 阈值才算同一个问题）
    """
    clusters: List[ProblemCluster] = []

    for issue in issues:
        best_cluster, best_similarity = None, -1.0

        for cluster in clusters:
            # 同年互斥：本年度已有成员的簇直接跳过（一次集合判断，不做相似度计算）
            if not cluster.accepts(issue):
                continue
            similarity = cluster.similarity_with(issue)
            # 相似度达到阈值，且比当前最优更相似，才换成这个簇
            if similarity >= threshold and similarity > best_similarity:
                best_cluster, best_similarity = cluster, similarity

        if best_cluster is not None:
            best_cluster.add(issue)
        else:
            clusters.append(create_cluster(issue))

    return clusters


# ====================== 输出组装 ======================

def to_duplicate_cluster(cluster: ProblemCluster) -> DuplicateCluster:
    """
    内部簇 -> 输出结构。
    整改状态、风险级别、问题原文等统计信息，统一取"最后一个年份"的那条记录。
    """
    latest = cluster.members[-1]
    return DuplicateCluster(
        clusterId=0,  # 排序后统一编号
        securityType=cluster.security_type,
        count=len(cluster.members),
        years=[m.year for m in cluster.members],
        riskLevel=latest.risk_level,
        rectified=latest.rectified,
        content=latest.content,
        occurrences=[
            ClusterOccurrence(
                year=m.year, content=m.content, riskLevel=m.risk_level, rectified=m.rectified,
            )
            for m in cluster.members
        ],
    )


def detect_duplicate_issues_from_items(
        items: List[YearlyIssues],
        start_year: int,
        end_year: int,
        threshold: float = DEFAULT_THRESHOLD,
) -> DuplicateDetectResponse:
    """
    重复问题检测核心流程（纯本地计算，不依赖任何模型服务）。

    :param items: 按年份组织的问题明细；可包含统计窗口之外的前一年（作为同比基准）
    :param start_year: 统计开始年份（含，int）
    :param end_year: 统计结束年份（含，int）
    :param threshold: 相似度阈值，>= 阈值才认为同一个问题；None 时用默认阈值 0.60

    统计规则：逐年输出 start_year ~ end_year；某年重复问题需与上一年比对，
    若上一年数据未传入，则该年重复问题数按 0 统计，其余统计不变。
    """

    # 展平 + 预分词
    flat_items = flatten_yearly_items(items)
    issues = build_issue_nodes(flat_items)

    # 步骤 1 按安全类型分类 -> 步骤 2 逐类聚类
    all_clusters: List[DuplicateCluster] = []
    ## 1. 先按照安全类型分组
    for security_type, group in group_by_security_type(issues).items():
        ## 2. 聚类分组
        for cluster in cluster_issues(group, threshold):
            all_clusters.append(to_duplicate_cluster(cluster))

    # 按出现次数降序统一编号（统计与输出共用同一份编号）
    all_clusters.sort(key=lambda c: (-c.count, c.securityType, c.riskLevel, c.content))
    for index, cluster in enumerate(all_clusters, start=1):
        cluster.clusterId = index

    duplicate_clusters = [c for c in all_clusters if c.count >= 2]

    # 统计窗口：start_year ~ end_year 逐年输出
    year_items = collect_year_items(flat_items)
    report_years = resolve_report_years(start_year, end_year)

    return DuplicateDetectResponse(
        threshold=threshold,
        totalItems=len(flat_items),
        duplicateClusterCount=len(duplicate_clusters),
        duplicateItemCount=sum(c.count for c in duplicate_clusters),
        clusters=duplicate_clusters,
        overview=build_duplicate_overview(duplicate_clusters),
        yearlyRectification=build_yearly_rectification(year_items, duplicate_clusters, report_years),
        yearlyDuplicates=build_yearly_duplicates(year_items, duplicate_clusters, report_years),
    )
