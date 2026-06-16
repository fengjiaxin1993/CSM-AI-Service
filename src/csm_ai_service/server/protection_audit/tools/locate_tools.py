from typing import List, Dict


def find_text_positions_in_json(clause_text: str, doc_id_list: List[str], json_result: Dict) -> List[Dict]:
    """
    在OCR JSON结果中查找文本位置
    """
    if not clause_text or not json_result:
        return []

    import re

    def normalize_text(text: str) -> str:
        """归一化文本：只保留中文、英文、数字"""
        text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
        text = text.upper()
        return re.sub(r'[^\w\u4e00-\u9fff]', '', text)

    def generate_keywords(text: str, normalized: bool = False) -> List[str]:
        """生成搜索关键词"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        keywords = []

        if len(lines) == 1:
            if normalized:
                text = normalize_text(text)

            text_len = len(text)

            if text_len <= 5:
                keywords.append(text)
            elif text_len <= 10:
                keywords.append(text[:5])
                keywords.append(text[-5:])
            elif text_len <= 20:
                keywords.append(text[:8])
                keywords.append(text[-8:])
                mid = text_len // 2
                keywords.append(text[mid - 4:mid + 4])
            else:
                keywords.append(text[:12])
                keywords.append(text[-12:])
                mid = text_len // 2
                keywords.append(text[mid - 6:mid + 6])
        else:
            for line in lines:
                if normalized:
                    line = normalize_text(line)

                line_len = len(line)
                if line_len < 2:
                    continue

                if line_len <= 8:
                    keywords.append(line)
                elif line_len <= 20:
                    keywords.append(line[:8])
                    if line_len > 10:
                        keywords.append(line[-8:])
                else:
                    keywords.append(line[:10])
                    keywords.append(line[-10:])
                    mid = line_len // 2
                    keywords.append(line[mid - 5:mid + 5])

        return list(set(k for k in keywords if len(k) >= 1))

    clause_text_clean = '\n'.join(line.strip() for line in clause_text.split('\n'))

    keywords_exact = generate_keywords(clause_text_clean, normalized=False)

    matches = []
    matched_block_ids = set()

    layout_results = json_result.get("layout_res_list", [])

    for layout_idx, layout_result in enumerate(layout_results):
        # 从 meta 中提取真实页码，兜底使用 layout_idx
        meta = layout_result.get("meta", {})
        page_num = meta.get("page_num", layout_idx) if isinstance(meta, dict) else layout_idx

        parsing_list = layout_result.get("parsing_res_list", [])

        for block in parsing_list:
            doc_id = block.get("doc_id")
            if doc_id not in doc_id_list:
                continue
            block_id = block.get("block_id")
            if block_id in matched_block_ids:
                continue

            block_content = block.get("block_content", "")
            if not block_content:
                continue

            matched = False
            for keyword in keywords_exact:
                if keyword in block_content:
                    matched = True
                    break

            if matched:
                matched_block_ids.add(block_id)
                matches.append({
                    "block_id": block_id,
                    "block_content": block_content,
                    "block_bbox": block.get("block_bbox", []),
                    "layout_idx": layout_idx,
                    "page_num": page_num,
                    "match_type": "exact"
                })
    return matches
