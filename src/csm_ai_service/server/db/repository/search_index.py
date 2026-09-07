"""
基于 jieba 的全文检索索引工具
提供分词、索引构建、全文检索功能
"""
import jieba

from csm_ai_service.utils import build_logger

logger = build_logger()

# 默认停用词
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "如何", "怎么", "为",
    "对", "与", "及", "或", "等", "但", "而", "从", "被", "把", "将", "已", "已",
    "未", "能", "可以", "可", "这个", "那个", "这些", "那些", "中", "里", "内",
    "外", "后", "前", "时", "下", "之", "以", "其", "如", "则", "此", "所", "该",
}


def tokenize(text: str) -> list:
    """
    使用 jieba 对文本进行分词，返回关键词列表（去停用词、去短词）
    """
    if not text or not isinstance(text, str):
        return []
    words = jieba.cut(text)
    # 过滤：去空格、去停用词、去单字（单个汉字区分度太低）
    return [w.strip() for w in words
            if w.strip() and w.strip() not in _STOP_WORDS and len(w.strip()) > 1]


def build_index_text(*texts: str) -> str:
    """
    将多个文本字段合并分词后，生成索引字符串（空格分隔）
    用于存储到 keywords_index 字段
    """
    combined = " ".join(t for t in texts if t)
    tokens = tokenize(combined)
    # 去重并保持顺序
    seen = set()
    unique_tokens = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)
    return " ".join(unique_tokens)


def search_by_index(index_text: str, query: str, top_k: int = 20) -> bool:
    """
    判断 query 是否命中索引。
    将 query 分词后，检查是否有词项命中 index_text。
    返回是否命中。
    """
    if not index_text or not query:
        return False
    query_tokens = tokenize(query)
    if not query_tokens:
        return False
    index_set = set(index_text.split())
    hit_count = sum(1 for t in query_tokens if t in index_set)
    return hit_count > 0


def calc_relevance_score(index_text: str, query: str) -> float:
    """
    计算 query 与索引的相似度得分（0~1）。
    基于 query 分词后在 index 中的命中率。
    """
    if not index_text or not query:
        return 0.0
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    index_set = set(index_text.split())
    hit_count = sum(1 for t in query_tokens if t in index_set)
    return round(hit_count / len(query_tokens), 4)
