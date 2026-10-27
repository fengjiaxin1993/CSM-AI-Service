"""
监测评估模块 —— 历年等保测评报告重复问题检测

功能：从历年的等保测评报告中找出相似的重复问题，并输出整改情况与历年统计。
输入：按年份组织的问题明细（每个年份对应一堆问题，每个问题包含问题描述、安全类型、风险级别、整改状态），
     以及统计开始年份与结束年份。
输出：
1. 每个重复问题簇（= 同一个根源重复问题）及其出现次数，簇内带上每一条的年份、原文、风险、整改状态；
2. 总览统计：重复簇个数、已整改/未整改个数（按簇内最后一年统计）、
   高风险/中风险/低风险分布（按最后一年统计）、安全类型分布；
3. 历年整改情况：统计窗口内每年已整改问题数量、重复问题数量（与上一年度比对）；
4. 历年重复问题及风险分布：每年重复问题条数、高/中/低风险条数。

处理逻辑：
1. 分组：仅按安全类型分类，同一安全类型的问题才互相比较（风险级别不参与分组）；
2. 相似度：仅使用 keyword 关键词法（jieba 分词 + 词集合 Jaccard），纯本地计算；
3. 逐年递进聚类：
   a) 最早年份的每条问题各自成簇；
   b) 之后每年逐条与已有簇比较，相似度 >= 阈值且该簇尚未出现本年度问题 -> 挂入相似度最高的簇；
   c) 同一簇内同一年份最多一条问题（同年互斥），不可挂入时新开一簇；
4. 统计：整改/风险按簇内最后一年信息统计；历年重复问题 = 今年出现且去年出现过的问题。

说明：
- 相似度实现见 text_similarity.py，统计口径见 issue_statistics.py；
- 统计窗口为 startYear ~ endYear（含首尾）；某年重复问题需与上一年比对，
  若上一年数据未传入，则该年重复问题数按 0 统计。
"""
import logging

from csm_ai_service.server.assessment.api_scheme import DuplicateDetectRequest, DuplicateDetectResponse
from csm_ai_service.server.assessment.cluster_method import detect_duplicate_issues_from_items

logger = logging.getLogger(__name__)


# ====================== API 入口 ======================

def detect_duplicate_issues(request: DuplicateDetectRequest) -> DuplicateDetectResponse:
    """
    重复问题检测 API 入口。

    输入：按年份组织的问题明细（每个年份对应一堆问题，字段为：
    问题描述 content、安全类型 securityType、风险级别 riskLevel、是否已整改 rectified），
    以及统计开始年份 startYear、结束年份 endYear。
    可选：相似度阈值 threshold（None 用默认 0.60）。
    输出：重复问题簇（含明细）+ 总览统计 + 历年整改 + 历年重复问题及风险分布。
    """
    return detect_duplicate_issues_from_items(
        items=request.items,
        start_year=request.startYear,
        end_year=request.endYear,
        threshold=request.threshold,
    )
