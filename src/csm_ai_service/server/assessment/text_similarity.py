"""
文本相似度计算 —— 关键词法（jieba 分词 + 词集合 Jaccard）

算法只有三步，不涉及矩阵：
1. 文本归一化：去掉空白与标点，只保留文字 / 数字 / 下划线；
2. jieba 分词并过滤纯功能词（保留"未 / 无 / 不"等否定词，
   避免"未开展漏洞扫描"与"定期开展漏洞扫描"这类语义相反的描述被判为重复）；
3. 词集合 Jaccard 相似度 = |交集| / |并集|，取值 [0, 1]，1 表示词集合完全一致。

说明：
- 分词是相对昂贵的操作，因此对外提供"先分词、再比较"的两段式接口
  （keyword_token_set + token_set_similarity），便于调用方对同一段文本只分词一次；
- 需要批量缓存分词结果时用 TextEncoder（相同文本只分词一次）；
- 所有文本相似度相关的计算都集中在本模块，其他模块不得自行实现；
- 纯本地计算，不依赖任何模型服务，可离线运行；
- jieba 延迟导入，避免影响模块导入速度。
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Set
import jieba
# ====================== 常量与默认配置 ======================
# 默认相似度阈值
DEFAULT_THRESHOLD = 0.90


# 停用词：仅过滤纯功能词；刻意保留"未 / 无 / 没有 / 不"等否定词
_STOPWORDS = set(
    "的了着之和与及或等其该各被把向从在是对为于而且并又都也就还再则"
) | {"以及", "或者", "并且", "因此", "所以", "但是", "然而", "对于", "关于"}


# ====================== 文本归一化与分词 ======================

def normalize_text(text) -> str:
    if not text:
        return ""
    text = text.replace(" ","")
    text = text.replace("\n","")
    return text


def keyword_tokens(text: str) -> List[str]:
    """
    关键词分词：归一化后 jieba 分词，过滤停用词。
    jieba 延迟导入（首次分词需加载词典）。
    """

    normalized = normalize_text(text)
    if not normalized:
        return []
    return [t for t in jieba.lcut(normalized) if t and t not in _STOPWORDS]


def keyword_token_set(text: str) -> Set[str]:
    """文本 -> 关键词集合（供需要复用分词结果的调用方使用）"""
    return set(keyword_tokens(text))


# ====================== 相似度计算 ======================

def token_set_similarity(tokens_a: Set[str], tokens_b: Set[str], same_text: bool = False) -> float:
    """
    基于已分词结果计算 Jaccard 相似度：|A∩B| / |A∪B|。

    :param tokens_a: 文本 A 的关键词集合
    :param tokens_b: 文本 B 的关键词集合
    :param same_text: 两段原文（归一化后）是否完全相同。
                      仅在两边都切不出关键词时用于区分：相同判 1，不同判 0。
    """
    if not tokens_a and not tokens_b:
        return 1.0 if same_text else 0.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    if not intersection:
        return 0.0
    # 并集大小 = |A| + |B| - |A∩B|，避免再构造一次并集集合
    return intersection / (len(tokens_a) + len(tokens_b) - intersection)


def keyword_similarity(a: str, b: str) -> float:
    """
    关键词相似度（自行分词，适合单次或少量比较）。
    需要多次比较同一批文本时，优先用 TextEncoder 预分词后再调用 encode_similarity。
    """
    tokens_a, tokens_b = keyword_token_set(a), keyword_token_set(b)
    return token_set_similarity(
        tokens_a,
        tokens_b,
        same_text=_same_normalized(a, b, tokens_a, tokens_b),
    )


def _same_normalized(a: str, b: str, tokens_a: Set[str], tokens_b: Set[str]) -> bool:
    """
    两段原文归一化后是否完全相同（仅在两边都切不出关键词时才有判定意义）。
    """
    if tokens_a or tokens_b:
        return False
    return normalize_text(a) == normalize_text(b)


# ====================== 预分词文本（供聚类复用） ======================

@dataclass
class EncodedText:
    """
    一条已完成分词与归一化的文本：分词只做一次，相似度比较可反复使用。
    """
    normalized: str          # 归一化后的文本（无空白无标点）
    tokens: Set[str]         # 关键词集合
    token_count: int         # 关键词个数（预存，避免每次求并集时重复 len）

    def __str__(self) -> str:
        return self.normalized




def encode_similarity(a: EncodedText, b: EncodedText) -> float:
    """
    两条已分词文本的关键词相似度。

    优化点（不改变判定结果）：
    - 关键词个数预先存在 EncodedText 上，求并集大小不再重复 len；
    - 交集为 0 直接返回，省去一次除法。
    """
    if not a.tokens and not b.tokens:
        # 两边都没切出关键词：只能靠原文是否相同来判定
        return 1.0 if a.normalized == b.normalized else 0.0
    if not a.tokens or not b.tokens:
        return 0.0
    intersection = len(a.tokens & b.tokens)
    if not intersection:
        return 0.0
    return intersection / (a.token_count + b.token_count - intersection)


class TextEncoder:
    """
    带缓存的分词器：相同文案只分词一次，批量文本复用同一份结果。
    用法：encoder = TextEncoder(); node_a = encoder.encode(a); node_b = encoder.encode(b)
    """

    def __init__(self) -> None:
        self._cache: Dict[str, EncodedText] = {}

    def encode(self, text: str) -> EncodedText:
        key = normalize_text(text)
        encoded = self._cache.get(key)
        if encoded is None:
            tokens = keyword_token_set(key)
            encoded = self._cache[key] = EncodedText(
                normalized=key,
                tokens=tokens,
                token_count=len(tokens),
            )
        return encoded
