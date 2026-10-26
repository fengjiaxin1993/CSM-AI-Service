"""
监测评估模块 —— 历年等保测评报告重复问题检测

功能：从历年的等保测评报告中找出相似的重复问题。
输入：按年份组织的问题明细（每个年份对应一堆问题，每个问题包含问题描述、安全类型、风险级别，均为字符串）。
输出：每个重复问题簇（= 同一个根源重复问题）及其出现次数，簇内带上每一条的年份、原文。

处理逻辑：
1. 首先根据安全类型和风险级别分类（字符串直接比较），
   只有安全类型和风险级别相同的才放入同一个比对分组；
2. 组内：计算两两文本相似度（纯本地计算，不依赖向量模型），支持多种方法（method 参数可选）：
   - keyword       jieba 分词 + 词集合 Jaccard（关键词重合度，默认）
   - edit_distance 字符级 Levenshtein 编辑距离归一化（字面改写）
   - ngram         字符 n-gram 余弦相似度（局部字序鲁棒）
   - combo         以上方法的加权融合（默认 keyword 0.4 / edit_distance 0.3 / ngram 0.3）
3. 连通聚类（并查集）：设定相似度阈值（各方法默认值不同，可用少量标注样本调参），
   任意一对相似度 >= 阈值 -> 执行并查集合并，归入同一个簇；
4. 跨年份约束（crossYearOnly，默认开启）：同一个簇内同一年份最多保留一条问题，
   即同一年份的所有问题不会被聚到一起，只有不同年份的问题才可能落在同一个聚类中；
5. 每一个簇 = 同一个根源重复问题，输出出现次数及簇内每条明细（年份、原文）。

说明：
- 输入全部为字符串（年份、问题描述、安全类型、风险级别），无需字典/编码转换；
- 各相似度方法的实现见 text_similarity.py。
"""
import logging

from csm_ai_service.server.assessment.api_scheme import DuplicateDetectRequest, DuplicateDetectResponse
from csm_ai_service.server.assessment.cluster_method import detect_duplicate_issues_from_items

logger = logging.getLogger(__name__)


# ====================== API 入口 ======================

def detect_duplicate_issues(request: DuplicateDetectRequest) -> DuplicateDetectResponse:
    """
    重复问题检测 API 入口。

    输入：按年份组织的问题明细（每个年份对应一堆问题，字段均为字符串：
    问题描述 content、安全类型 securityType、风险级别 riskLevel）。
    可选：相似度方法 method（keyword / edit_distance / ngram / combo）、
    相似度阈值 threshold（None 用方法默认）、融合权重 methodWeights（combo 时生效）。
    输出：每个重复问题簇（= 同一个根源重复问题）、出现次数，簇内带上每一条的年份、原文。
    """
    return detect_duplicate_issues_from_items(
        items=request.items,
        threshold=request.threshold,
        method=request.method,
        include_singletons=request.includeSingletons,
        method_weights=request.methodWeights,
        cross_year_only=request.crossYearOnly,
    )
