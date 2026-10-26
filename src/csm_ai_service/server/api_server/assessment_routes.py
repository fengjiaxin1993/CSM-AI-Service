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

    输入（按年份组织，字段均为字符串）：2026年对应一堆问题，2027年对应一堆问题。
    {
      "items": [
        {"year": "2026", "issues": [
          {"content": "未对登录的用户进行身份标识唯一性检查", "securityType": "安全计算环境", "riskLevel": "中"},
          {"content": "网络设备未启用安全的远程管理协议", "securityType": "安全区域边界", "riskLevel": "低"}
        ]},
        {"year": "2027", "issues": [
          {"content": "未对登录的用户进行身份标识唯一性检查", "securityType": "安全计算环境", "riskLevel": "中"}
        ]}
      ],
      "method": "keyword",
      "threshold": 0.60
    }

    处理逻辑：
    1. 按（安全类型, 风险级别）字符串分组，只有两者都相同的问题才会互相比较；
    2. 组内计算两两文本相似度（纯本地计算，不依赖向量模型），method 可选：
       - keyword       jieba 分词 + 词集合 Jaccard（关键词重合度，默认）
       - edit_distance 字符级 Levenshtein 编辑距离归一化（捕捉字面改写）
       - ngram         字符 n-gram 余弦相似度（局部字序鲁棒）
       - combo         多方法加权融合（methodWeights 自定义权重，默认 keyword 0.4 / edit_distance 0.3 / ngram 0.3）
    3. 连通聚类（并查集）：任意一对相似度 >= threshold 即合并进同一个簇；
       threshold 不传时用方法默认值（keyword 0.60 / edit_distance 0.75 / ngram 0.70 / combo 0.70），可用少量标注样本调参；
    4. 每一个簇 = 同一个根源重复问题，输出出现次数及簇内每一条的年份、原文。

    输出：重复问题簇列表（按出现次数降序），包含 method、threshold、count（出现次数）、years、representativeContent（代表性表述）、occurrences（年份+原文明细）。
    """
    try:
        result = detect_duplicate_issues(request)
        return ApiResponse(success=True, message="success", data=result.model_dump())
    except Exception as e:
        logger.error(f"重复问题检测失败: {e}", exc_info=True)
        return ApiResponse(success=False, message=f"重复问题检测失败: {str(e)}")
