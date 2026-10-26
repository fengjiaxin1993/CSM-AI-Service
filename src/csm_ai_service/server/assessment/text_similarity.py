"""
文本相似度计算方法集合 —— 供重复问题检测的组内两两比对使用

支持的方法（method 参数取值）：
- keyword       关键词：jieba 分词（去除功能词，保留否定词）后计算词集合 Jaccard 相似度
- edit_distance 编辑距离：字符级 Levenshtein 距离归一化（1 - dist/max_len），捕捉字面改写
- ngram         字符 n-gram：字符 bigram 计数向量的余弦相似度，对局部字序变化鲁棒
- combo         融合：以上方法的加权平均（默认 keyword 0.4 / edit_distance 0.3 / ngram 0.3，
                可通过 weights 自定义）

说明：
- 各方法相似度均归一化到 [0, 1]，1 表示完全相同；
- 各方法有不同的合理阈值区间（见 DEFAULT_THRESHOLDS），均为经验起点，需用少量标注样本调参；
- 所有方法均为纯本地计算，不依赖任何模型服务，可离线运行；
- jieba 为延迟导入，避免影响模块导入速度。
"""
import re
from collections import Counter
from typing import Dict, List, Optional, Sequence

import numpy as np

# ====================== 方法常量与默认配置 ======================

METHOD_KEYWORD = "keyword"
METHOD_EDIT_DISTANCE = "edit_distance"
METHOD_NGRAM = "ngram"
METHOD_COMBO = "combo"

SIMILARITY_METHODS = (
    METHOD_KEYWORD,
    METHOD_EDIT_DISTANCE,
    METHOD_NGRAM,
    METHOD_COMBO,
)

# 各方法默认相似度阈值（经验起点，需用少量标注样本调参）：
# - keyword 为词集合 Jaccard，整体数值偏低，阈值相应调低；
# - edit_distance 对长文本的字面改写较敏感，阈值取中高；
# - combo 为多方法加权平均，阈值按默认权重加权各方法阈值而定。
DEFAULT_THRESHOLDS = {
    METHOD_KEYWORD: 0.60,
    METHOD_EDIT_DISTANCE: 0.75,
    METHOD_NGRAM: 0.70,
    METHOD_COMBO: 0.70,
}

# combo 融合默认权重：关键词重合度为主，字面方法为辅
DEFAULT_COMBO_WEIGHTS = {
    METHOD_KEYWORD: 0.4,
    METHOD_EDIT_DISTANCE: 0.3,
    METHOD_NGRAM: 0.3,
}

# 关键词法停用词：仅过滤纯功能词；刻意保留"未/无/没有/不"等否定词，
# 以区分"未开展漏洞扫描"与"定期开展漏洞扫描"这类语义相反的描述
_STOPWORDS = set(
    "的了着之和与及或等其该各被把向从在是对为于而且并又都也就还再则"
) | {"以及", "或者", "并且", "因此", "所以", "但是", "然而", "对于", "关于"}

# 字符 n-gram 的 n
_DEFAULT_NGRAM = 2


# ====================== 文本归一化 ======================

def normalize_text(text) -> str:
    """去除空白与标点（中英文），仅保留文字/数字/下划线，用于相似度计算"""
    if not text:
        return ""
    return re.sub(r"[^\w]+", "", str(text))


def _same_raw(a, b) -> bool:
    return (a or "") == (b or "")


# ====================== 编辑距离（Levenshtein） ======================

def edit_distance(a: str, b: str) -> int:
    """
    字符级 Levenshtein 编辑距离（插入/删除/替换各计 1 次），O(len(a)*len(b))。
    输入先经 normalize_text 归一化，消除空白与标点差异。
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a  # 让 b 为较短串，减小滚动数组宽度
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,        # 删除
                cur[j - 1] + 1,     # 插入
                prev[j - 1] + (ca != cb),  # 替换
            ))
        prev = cur
    return prev[-1]


def edit_distance_similarity(a: str, b: str) -> float:
    """
    编辑距离相似度 = 1 - dist / max(len_a, len_b)，归一化到 [0, 1]。
    完全相同为 1；"登录/登陆"这类个别错别字差异会得到接近 1 的分数。
    """
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 1.0 if _same_raw(a, b) else 0.0
    longest = max(len(na), len(nb))
    return 1.0 - edit_distance(na, nb) / longest


def edit_distance_similarity_matrix(texts: Sequence[str]) -> np.ndarray:
    """两两编辑距离相似度矩阵（n x n）"""
    n = len(texts)
    matrix = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        matrix[i, i] = 1.0
        for j in range(i + 1, n):
            sim = edit_distance_similarity(texts[i], texts[j])
            matrix[i, j] = matrix[j, i] = sim
    return matrix


# ====================== 关键词（jieba 分词 + Jaccard） ======================

def keyword_tokens(text: str) -> List[str]:
    """
    关键词分词：归一化后 jieba 分词，过滤停用词。
    jieba 延迟导入（首次分词需加载词典）。
    """
    import jieba
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [t for t in jieba.lcut(normalized) if t and t not in _STOPWORDS]


def keyword_similarity(a: str, b: str) -> float:
    """
    关键词相似度：分词后词集合的 Jaccard 系数 |A∩B| / |A∪B|。
    语义无关、纯字面词汇重合度，适合捕捉"同词不同句式"的重复描述。
    """
    tokens_a = set(keyword_tokens(a))
    tokens_b = set(keyword_tokens(b))
    if not tokens_a and not tokens_b:
        return 1.0 if _same_raw(a, b) else 0.0
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def keyword_similarity_matrix(texts: Sequence[str]) -> np.ndarray:
    """两两关键词 Jaccard 相似度矩阵（n x n），分词结果预计算避免重复切词"""
    n = len(texts)
    token_sets = [set(keyword_tokens(t)) for t in texts]
    matrix = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        matrix[i, i] = 1.0
        for j in range(i + 1, n):
            sa, sb = token_sets[i], token_sets[j]
            if not sa and not sb:
                sim = 1.0 if _same_raw(texts[i], texts[j]) else 0.0
            elif not sa or not sb:
                sim = 0.0
            else:
                sim = len(sa & sb) / len(sa | sb)
            matrix[i, j] = matrix[j, i] = sim
    return matrix


# ====================== 字符 n-gram 余弦 ======================

def _char_ngrams(s: str, n: int = _DEFAULT_NGRAM) -> Counter:
    if not s:
        return Counter()
    if len(s) < n:
        return Counter([s])
    return Counter(s[i:i + n] for i in range(len(s) - n + 1))


def ngram_similarity(a: str, b: str, n: int = _DEFAULT_NGRAM) -> float:
    """
    字符 n-gram 余弦相似度：以相邻 n 个字符为单元构建计数向量后求余弦。
    对局部字序调整、少量增删字符比编辑距离更宽容。
    """
    ga = _char_ngrams(normalize_text(a), n)
    gb = _char_ngrams(normalize_text(b), n)
    if not ga and not gb:
        return 1.0 if _same_raw(a, b) else 0.0
    if not ga or not gb:
        return 0.0
    dot = sum(cnt * gb.get(g, 0) for g, cnt in ga.items())
    norm_a = sum(cnt * cnt for cnt in ga.values()) ** 0.5
    norm_b = sum(cnt * cnt for cnt in gb.values()) ** 0.5
    return dot / (norm_a * norm_b)


def ngram_similarity_matrix(texts: Sequence[str], n: int = _DEFAULT_NGRAM) -> np.ndarray:
    """两两字符 n-gram 余弦相似度矩阵（n x n），gram 计数预计算"""
    grams = [_char_ngrams(normalize_text(t), n) for t in texts]
    norms = [sum(c * c for c in g.values()) ** 0.5 for g in grams]
    size = len(texts)
    matrix = np.zeros((size, size), dtype=np.float64)
    for i in range(size):
        matrix[i, i] = 1.0
        for j in range(i + 1, size):
            ga, gb = grams[i], grams[j]
            if not ga and not gb:
                sim = 1.0 if _same_raw(texts[i], texts[j]) else 0.0
            elif not ga or not gb or norms[i] == 0.0 or norms[j] == 0.0:
                sim = 0.0
            else:
                dot = sum(cnt * gb.get(g, 0) for g, cnt in ga.items())
                sim = dot / (norms[i] * norms[j])
            matrix[i, j] = matrix[j, i] = sim
    return matrix


# ====================== 多方法融合 ======================

def combine_similarity_matrices(
        matrices: Dict[str, np.ndarray],
        weights: Dict[str, float],
) -> np.ndarray:
    """
    加权融合多个相似度矩阵：sum(w_i * M_i) / sum(w_i)。
    权重自动归一化，无需手动保证和为 1。
    """
    active = {m: w for m, w in weights.items() if w > 0}
    if not active:
        raise ValueError("融合权重全为 0 或为空，至少需要一个正权重")
    total = sum(active.values())
    shape = None
    result = None
    for method, weight in active.items():
        matrix = matrices[method]
        if shape is None:
            shape = matrix.shape
            result = np.zeros(shape, dtype=np.float64)
        elif matrix.shape != shape:
            raise ValueError(f"融合矩阵形状不一致: {method} 为 {matrix.shape}, 期望 {shape}")
        result += (weight / total) * matrix
    return result


def _resolve_combo_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    """解析 combo 融合权重：None 用默认；校验方法合法、权重非负、总和为正"""
    resolved = dict(DEFAULT_COMBO_WEIGHTS) if weights is None else dict(weights)
    if not resolved:
        raise ValueError("融合权重不能为空")
    for method, weight in resolved.items():
        if method not in SIMILARITY_METHODS:
            raise ValueError(f"融合权重中包含未知方法: {method}，可选: {', '.join(SIMILARITY_METHODS)}")
        if weight < 0:
            raise ValueError(f"融合权重不能为负数: {method}={weight}")
    if sum(resolved.values()) <= 0:
        raise ValueError("融合权重总和必须大于 0")
    return resolved


# ====================== 方法分发 ======================

def resolve_threshold(method: str, threshold: Optional[float] = None) -> float:
    """阈值解析：None 时返回该方法的默认阈值；同时校验方法合法性"""
    if method not in DEFAULT_THRESHOLDS:
        raise ValueError(f"未知的相似度方法: {method}，可选: {', '.join(SIMILARITY_METHODS)}")
    if threshold is None:
        return DEFAULT_THRESHOLDS[method]
    return float(threshold)


def build_group_similarity_matrix(
        method: str,
        texts: Sequence[str],
        weights: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """
    构建一组文本的两两相似度矩阵（方法分发入口）。

    :param method: 相似度方法（keyword / edit_distance / ngram / combo）
    :param texts: 组内文本列表
    :param weights: combo 融合权重，None 用默认 {keyword:0.4, edit_distance:0.3, ngram:0.3}
    """
    if method == METHOD_KEYWORD:
        return keyword_similarity_matrix(texts)

    if method == METHOD_EDIT_DISTANCE:
        return edit_distance_similarity_matrix(texts)

    if method == METHOD_NGRAM:
        return ngram_similarity_matrix(texts)

    if method == METHOD_COMBO:
        resolved_weights = _resolve_combo_weights(weights)
        matrices: Dict[str, np.ndarray] = {}
        for sub_method, weight in resolved_weights.items():
            if weight <= 0:
                continue
            matrices[sub_method] = build_group_similarity_matrix(sub_method, texts, weights=None)
        return combine_similarity_matrices(matrices, resolved_weights)

    raise ValueError(f"未知的相似度方法: {method}，可选: {', '.join(SIMILARITY_METHODS)}")
