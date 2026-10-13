import difflib
from typing import List, Dict
import re

import jieba

from csm_ai_service.server.warning_report_audit.tools.pdf_parser_tools import TextBlock
# 停用词词典
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "如何", "怎么", "为",
    "对", "与", "及", "或", "等", "但", "而", "从", "被", "把", "将", "已", "已",
    "未", "能", "可以", "可", "这个", "那个", "这些", "那些", "中", "里", "内",
    "外", "后", "前", "时", "下", "之", "以", "其", "如", "则", "此", "所", "该",
}

def normalize_text(text: str) -> str:
    """归一化文本：只保留中文、英文、数字"""
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    text = text.upper()
    return re.sub(r'[^\w\u4e00-\u9fff]', '', text)


def calc_keyword_hit_count(block_text: str, keywords: set) -> int:
    """统计block命中关键词数量，用于前置粗筛提速"""
    norm_blk = normalize_text(block_text)
    hit_cnt = 0
    for kw in keywords:
        if kw in norm_blk:
            hit_cnt += 1
    return hit_cnt


def extract_keywords_by_jieba(text: str) -> set:
    """jieba分词，过滤停用词、单字，提取关键词集合"""
    norm_text = normalize_text(text)
    words = jieba.lcut(norm_text)
    keywords = set()
    for w in words:
        w_strip = w.strip()
        if w_strip not in STOP_WORDS and len(w_strip) > 1:
            keywords.add(w_strip)
    return keywords



def is_block_fuzzy_substring(target_full: str, block: str, sim_thresh: float = 0.75) -> bool:
    """
    核心函数：使用 SequenceMatcher.find_longest_match
    判断 block 是否是 target_full 中的片段（允许少量OCR误差）
    ratio = 【最长连续匹配字符长度】 / block归一化后的总长度
    :param target_full: 目标text原始字符串
    :param block: block_content文本
    :param sim_thresh: 阈值 0~1
    :return: True=属于原文片段；False=不是
    """
    norm_full = normalize_text(target_full)
    norm_blk = normalize_text(block)
    blk_len = len(norm_blk)
    full_len = len(norm_full)

    if blk_len == 0 or blk_len > full_len:
        return False

    sm = difflib.SequenceMatcher(None, norm_full, norm_blk)
    match = sm.find_longest_match(0, full_len, 0, blk_len)
    max_match_len = match.size

    if max_match_len <= 0:
        return False

    ratio = max_match_len / blk_len
    return ratio >= sim_thresh



def find_text_positions_in_blocks(clause_text: str, text_blocks:List[TextBlock]) -> List[Dict]:
    """
    在 textBlocks 找到位置
    """
    if not clause_text or len(text_blocks) == 0:
        return []
    keywords_set = extract_keywords_by_jieba(clause_text)
    matches = []
    matched_block_ids = set()


    for block in text_blocks:
        block_id = block.block_id
        block_content = block.text
        page_num = block.page_num
        if not block_content:
            continue
        hit_count = calc_keyword_hit_count(block_content, keywords_set)
        # step1 粗筛， 挑出关键词命中的， 命中关键词<=3个的过滤
        if hit_count < 3: # 找出命中>=3个关键词的
            continue
        # step2 精筛， 挑出相似度高的
        match_flag =  is_block_fuzzy_substring(clause_text, block_content, sim_thresh=0.7)
        if not match_flag:
            continue


        matched_block_ids.add(block_id)
        matches.append({
            "block_id": block_id,
            "block_content": block_content,
            "block_bbox": block.bbox,
            "page_num": page_num
        })
    return matches
