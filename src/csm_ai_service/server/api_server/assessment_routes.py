"""
监测评估模块 API 路由
"""
from fastapi import APIRouter

from csm_ai_service.server.assessment.duplicate_issue_detect import (
    DuplicateDetectRequest,
    detect_duplicate_issues,
)
from csm_ai_service.server.utils import ApiResponse
from csm_ai_service.utils import build_logger

logger = build_logger()

monitoring_assessment_router = APIRouter(prefix="/assessment", tags=["检测评估"])


@monitoring_assessment_router.post(
    "/detect_duplicate_issues",
    response_model=ApiResponse,
    summary="历年等保测评报告-相似重复问题检测",
)
def detect_duplicate_issues_api(request: DuplicateDetectRequest):
    """
    从历年的等保测评报告中找出相似的重复问题。
    处理逻辑：
    1. 仅按安全类型分组，同一安全类型的问题才互相比较（风险级别只用于统计，不参与分组）；
    2. 相似度统一使用 keyword 关键词法（jieba 分词 + 词集合 Jaccard，纯本地计算，不依赖向量模型）；
    3. 逐年递进聚类：
       a) 最早年份的每条问题各自成簇；
       b) 之后每年逐条与已有簇比较，只与簇内【最后年份】的成员计算相似度，
          相似度 >= threshold 且该簇尚未出现本年度问题 -> 挂入相似度最高的簇；
       c) 同一簇内同一年份最多一条问题（同年互斥），不可挂入时新开一簇；
       threshold 不传时用默认值 0.90；
    4. 每一个簇 = 同一个根源重复问题，输出出现次数及簇内每一条的年份、原文、风险、整改状态；
    5. 统计窗口 = startYear ~ endYear（含首尾），逐年输出；某年重复问题需与上一年比对，
       若上一年数据未传入（如 startYear=2024 但未传 2023 的数据），该年重复问题数按 0 统计，其余统计不变。

    输出：
    - clusters：重复问题簇列表（按出现次数降序），含 count（出现次数）、years、riskLevel / rectified / content
      （均取簇内最后一个年份的信息）、occurrences（年份+原文+风险+整改状态明细）；
    - overview：总览统计，含 duplicateClusterCount（重复簇个数）、
      rectifiedCount / unrectifiedCount（按最后一年统计的已/未整改簇数）、
      riskDistribution（高/中/低风险簇数，按最后一年统计）、securityTypeDistribution（安全类型分布）；
    - yearlyRectification：历年整改情况，含每年问题总数、已整改数量、未整改数量、重复问题数量（与去年比对）；
    - yearlyDuplicates：历年重复问题及风险分布，含每年问题总数、重复问题条数、riskDistribution（高/中/低风险条数）。
    """
    try:
        result = detect_duplicate_issues(request)
        return ApiResponse(success=True, message="success", data=result.model_dump())
    except Exception as e:
        logger.error(f"重复问题检测失败: {e}", exc_info=True)
        return ApiResponse(success=False, message=f"重复问题检测失败: {str(e)}")
