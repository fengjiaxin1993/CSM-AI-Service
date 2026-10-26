# ====================== 聚类算法 ======================
from typing import List, Dict, Optional, Tuple

import numpy as np

from csm_ai_service.server.assessment.api_scheme import YearlyIssues, FlatIssue, DuplicateDetectResponse, \
    DuplicateCluster, ClusterOccurrence
from csm_ai_service.server.assessment.text_similarity import (
    METHOD_KEYWORD,
    build_group_similarity_matrix,
    resolve_threshold,
)


def flatten_yearly_items(yearly_items: List[YearlyIssues]) -> List[FlatIssue]:
    """把按年份组织的输入展平成（年份, 问题）列表，跳过空问题描述"""
    flat: List[FlatIssue] = []
    for yearly in yearly_items:
        for issue in yearly.issues:
            if (issue.content or "").strip():
                flat.append(FlatIssue(
                    year=yearly.year,
                    content=issue.content,
                    security_type=issue.securityType,
                    risk_level=issue.riskLevel,
                ))
            else:
                print(f"跳过空问题描述: year={yearly.year}")
    return flat


class UnionFind:
    """并查集（路径压缩 + 按秩合并），用于相似度连通聚类"""

    def __init__(self, n: int):
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # 路径压缩
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1
        return True

    def clusters(self) -> Dict[int, List[int]]:
        """返回 {根节点: [成员下标列表]} 的连通分量字典"""
        groups: Dict[int, List[int]] = {}
        for i in range(len(self._parent)):
            groups.setdefault(self.find(i), []).append(i)
        return groups


def cluster_by_similarity(
        sim_matrix: np.ndarray,
        threshold: float,
        years: Optional[List[str]] = None,
) -> Dict[int, List[int]]:
    """
    连通聚类（并查集）：任意一对相似度 >= threshold 即合并进同一个簇。

    :param sim_matrix: n x n 相似度矩阵
    :param threshold: 相似度阈值
    :param years: 可选，长度 n 的年份列表（与矩阵下标一一对应）。
                  传入时启用"同一年份互斥"约束：
                  1) 同一年份的两条问题无论多相似都不合并（一个簇里同一年的问题最多一条）；
                  2) 合并前检查两个簇的年份集合是否相交，相交则放弃合并，
                     避免 A-B、B-C 链式合并把同一年份的两条问题间接放进同一簇。
    返回 {簇根节点: [成员下标列表]}
    """
    n = sim_matrix.shape[0]
    uf = UnionFind(n)

    # 约束模式：按相似度从高到低顺序尝试合并，贪心保证同一年份在一个簇内唯一
    if years is not None and len(years) != n:
        raise ValueError(f"years 长度({len(years)}) 与相似度矩阵维度({n})不一致")

    if years is None:
        for i in range(n):
            for j in range(i + 1, n):
                if sim_matrix[i, j] >= threshold:
                    uf.union(i, j)
        return uf.clusters()

    # 每个簇根节点维护已占用年份集合
    cluster_years: Dict[int, set] = {i: ({years[i]} if years[i] else set()) for i in range(n)}

    pairs = [
        (sim_matrix[i, j], i, j)
        for i in range(n)
        for j in range(i + 1, n)
        if sim_matrix[i, j] >= threshold and years[i] != years[j]
    ]
    pairs.sort(key=lambda p: -p[0])

    for _sim, i, j in pairs:
        ri, rj = uf.find(i), uf.find(j)
        if ri == rj:
            continue
        if cluster_years[ri] & cluster_years[rj]:
            # 合并后会出现同一年份的两条问题，违反约束
            continue
        uf.union(ri, rj)
        root = uf.find(ri)
        merged = cluster_years[ri] | cluster_years[rj]
        cluster_years[ri] = merged
        cluster_years[rj] = merged
        cluster_years[root] = merged

    return uf.clusters()


def group_items(flat_items: List[FlatIssue]) -> Dict[Tuple[str, str], List[int]]:
    """
    步骤 1 分组：按（安全类型, 风险级别）字符串分类（仅清理空白，不做编码转换），
    只有两者的清理结果都相同才进入同一个比对分组。
    返回 {分组键: [该组元素在展平列表中的全局下标]}
    """
    groups: Dict[Tuple[str, str], List[int]] = {}
    for idx, item in enumerate(flat_items):
        key = (item.security_type, item.risk_level)
        groups.setdefault(key, []).append(idx)
    return groups


def detect_duplicate_issues_from_items(
        items: List[YearlyIssues],
        threshold: Optional[float] = None,
        method: str = METHOD_KEYWORD,
        include_singletons: bool = False,
        method_weights: Optional[Dict[str, float]] = None,
        cross_year_only: bool = True,
) -> DuplicateDetectResponse:
    """
    重复问题检测核心流程（纯本地计算，不依赖任何模型服务）。

    :param items: 按年份组织的问题明细（每个年份对应一堆问题）
    :param threshold: 相似度阈值，任意一对相似度 >= 阈值即合并进同一簇；
                     None 时使用该方法的默认阈值（keyword 0.60 /
                      edit_distance 0.75 / ngram 0.70 / combo 0.70）
    :param method: 相似度计算方法：
                   keyword       jieba 分词 + 词集合 Jaccard（关键词重合度，默认）
                   edit_distance 字符级 Levenshtein 编辑距离归一化（字面改写）
                   ngram         字符 n-gram 余弦（局部字序鲁棒）
                   combo         多方法加权融合（权重见 method_weights）
    :param include_singletons: 是否输出仅出现一次的问题簇
    :param method_weights: combo 融合权重，如 {"keyword": 0.4, "edit_distance": 0.3, "ngram": 0.3}
    :param cross_year_only: 是否启用"跨年份"约束（默认 True）：
                            同一个聚簇内不允许出现同一年的两条问题，
                            即只有不同年份的问题才可能被合并到同一个聚类中
    """
    # 阈值与方法校验（未知方法在此抛出 ValueError）
    threshold = resolve_threshold(method, threshold)

    # 展平：年份 -> 问题列表 => (年份, 问题) 记录，过滤空问题描述
    flat_items = flatten_yearly_items(items)

    clusters_out: List[DuplicateCluster] = []
    group_count = 0

    if flat_items:
        # 步骤 1：按（安全类型, 风险级别）字符串分组
        groups = group_items(flat_items)
        group_count = len(groups)

        # 步骤 2 + 3：组内两两相似度（按 method 分发计算）-> 并查集连通聚类
        for (sec_key, risk_key), indices in groups.items():
            n = len(indices)
            if n < 2:
                if include_singletons:
                    clusters_out.append(_build_singleton_cluster(0, sec_key, risk_key, flat_items[indices[0]]))
                continue

            group_texts = [flat_items[i].content for i in indices]
            sim_matrix = build_group_similarity_matrix(method, group_texts, weights=method_weights)
            group_years = [flat_items[i].year for i in indices] if cross_year_only else None
            components = cluster_by_similarity(sim_matrix, threshold, years=group_years)

            for members in components.values():
                if len(members) < 2 and not include_singletons:
                    continue
                clusters_out.append(_build_cluster(sec_key, risk_key, members, indices, sim_matrix, flat_items))

    # 按出现次数降序编排簇编号
    clusters_out.sort(key=lambda c: (-c.count, c.securityType, c.riskLevel, c.clusterId))
    for i, cluster in enumerate(clusters_out):
        cluster.clusterId = i + 1

    duplicate_clusters = [c for c in clusters_out if c.count >= 2]
    duplicate_item_count = sum(c.count for c in duplicate_clusters)

    return DuplicateDetectResponse(
        threshold=threshold,
        method=method,
        totalItems=len(flat_items),
        groupCount=group_count,
        duplicateClusterCount=len(duplicate_clusters),
        duplicateItemCount=duplicate_item_count,
        clusters=clusters_out,
    )


def _build_singleton_cluster(
        cluster_id: int,
        security_type: str,
        risk_level: str,
        item: FlatIssue,
) -> DuplicateCluster:
    return DuplicateCluster(
        clusterId=cluster_id,
        securityType=security_type,
        riskLevel=risk_level,
        count=1,
        years=[item.year] if item.year else [],
        representativeContent=item.content,
        occurrences=[ClusterOccurrence(year=item.year, content=item.content)],
    )


def _build_cluster(
        security_type: str,
        risk_level: str,
        members: List[int],
        indices: List[int],
        sim_matrix: np.ndarray,
        flat_items: List[FlatIssue],
) -> DuplicateCluster:
    """根据簇成员构建输出结构；代表性问题取簇内平均相似度最高者（medoid）"""
    # 代表性问题（medoid）：仅对 >= 2 的簇计算
    representativeContent = ""
    if len(members) >= 2:
        sub_sim = sim_matrix[np.ix_(members, members)]
        avg_sim = sub_sim.mean(axis=1)
        rep_local = members[int(np.argmax(avg_sim))]
        rep = flat_items[indices[rep_local]]
        representativeContent = rep.content

    member_items = [flat_items[indices[m]] for m in members]
    member_items.sort(key=lambda it: it.year)
    years = sorted({it.year for it in member_items if it.year})

    return DuplicateCluster(
        clusterId=0,  # 排序后统一编排
        securityType=security_type,
        riskLevel=risk_level,
        count=len(member_items),
        years=years,
        representativeContent=representativeContent,
        occurrences=[ClusterOccurrence(year=it.year, content=it.content) for it in member_items],
    )

