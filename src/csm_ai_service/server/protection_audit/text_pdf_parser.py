"""
文本类型 PDF 解析器 - 基于 PyMuPDF (fitz)

核心功能：
1. 识别目录页，提取目录结构
2. 提取原文，去除倾斜水印
3. 提取表格，去除水印，转为 Markdown
4. 去除每页最下方的纯数字页码
5. 标题识别（编号模式 + 附件模式 + 目录匹配 + 字号加粗）
6. 生成 Markdown 文件
"""
import re
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import fitz
import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────── 数据结构 ────────────────────────────────

@dataclass
class TextBlock:
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    page_num: int
    block_num: int# 0-based
    block_id: str # block_page_block_line
    block_type: str = "text"
    is_in_table: bool = False # 是否在表格中



@dataclass
class TableBlock:
    bbox: Tuple[float, float, float, float]
    page_num: int
    row_count: int = 0
    col_count: int = 0
    markdown: str = ""
    cells: List[List[Optional[str]]] = field(default_factory=list)

@dataclass
class PageInfo:
    page_num: int       # 0-based
    width: float
    height: float
    blocks: List[TextBlock] = field(default_factory=list)
    tables: List[TableBlock] = field(default_factory=list)
    is_toc_page: bool = False
    markdown: str = ""


@dataclass
class PdfParseResult:
    pdf_path: str
    total_pages: int
    pages: List[PageInfo] = field(default_factory=list)
    markdown: str = ""


# ──────────────────────────────── 通用工具 ────────────────────────────────

def _is_line_tilted(dir_vec: Tuple[float, float]) -> bool:
    """倾斜/旋转文字行判断（偏离水平/竖直 >5° 即视为水印）"""
    dx, dy = dir_vec
    if dx == 0 and dy == 0:
        return True
    angle_h = math.degrees(math.atan2(abs(dy), abs(dx)))
    angle_v = math.degrees(math.atan2(abs(dx), abs(dy)))
    return angle_h > 5 and angle_v > 5

def _block_center_in_table(bbox, table_bboxes) -> bool:
    """文本块中心是否落在某个表格区域内"""
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    return any(tx0 <= cx <= tx1 and ty0 <= cy <= ty1 for tx0, ty0, tx1, ty1 in table_bboxes)


# ──────────────────────────────── 表格识别（去水印） ────────────────────────────────

def _collect_clean_spans(page_dict, page_w, page_h) -> List[Dict]:
    """收集页面中所有非倾斜 span（用于重建表格单元格、排除水印）"""
    spans: List[Dict] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            if _is_line_tilted(line.get("dir", (1, 0))):
                continue
            for span in line.get("spans", []):
                t = span.get("text", "")
                if not t.strip():
                    continue
                bb = span.get("bbox", (0, 0, 0, 0))
                spans.append({
                    "text": t,
                    "bbox": bb,
                    "y_mid": (bb[1] + bb[3]) / 2,
                    "x_mid": (bb[0] + bb[2]) / 2,
                })
    return spans


def _rebuild_table_cells(tab, clean_spans) -> Optional[List[List[Optional[str]]]]:
    """从非倾斜 span 重建表格单元格内容，排除水印"""
    if not hasattr(tab, "rows") or not tab.rows:
        return None
    rows: List[List[Optional[str]]] = []
    for row in tab.rows:
        if not hasattr(row, "cells") or not row.cells:
            return None
        row_texts: List[Optional[str]] = []
        for cell in row.cells:
            if cell is None:
                row_texts.append(None)
                continue
            cx0, cy0, cx1, cy1 = cell[:4]
            matching = [
                s for s in clean_spans
                if cx0 - 2 <= s["x_mid"] <= cx1 + 2 and cy0 - 2 <= s["y_mid"] <= cy1 + 2
            ]
            if matching:
                matching.sort(key=lambda s: (round(s["y_mid"], 0), s["x_mid"]))
                groups: List[List[Dict]] = [[matching[0]]]
                for s in matching[1:]:
                    if abs(s["y_mid"] - groups[-1][0]["y_mid"]) < 3:
                        groups[-1].append(s)
                    else:
                        groups.append([s])
                lines = []
                for g in groups:
                    g.sort(key=lambda s: s["x_mid"])
                    lines.append("".join(s["text"] for s in g))
                row_texts.append("\n".join(lines).strip() or None)
            else:
                row_texts.append(None)
        rows.append(row_texts)
    return rows


def _cells_to_md(cells: List[List[Optional[str]]]) -> str:
    """二维单元格列表 → Markdown 表格"""
    if not cells or not cells[0]:
        return ""
    ncols = len(cells[0])
    lines = []
    for i, row in enumerate(cells):
        padded = [(c or "") for c in row] + [""] * max(0, ncols - len(row))
        clean = [c.replace("\n", " ").strip() for c in padded]
        lines.append("| " + " | ".join(clean) + " |")
        if i == 0:
            lines.append("|" + "|".join(["---"] * ncols) + "|")
    return "\n".join(lines)


def _extract_tables(page, page_idx, page_dict, page_w, page_h) -> List[TableBlock]:
    """识别页面表格，用非倾斜 span 重建单元格（去水印），转为 Markdown"""
    tables: List[TableBlock] = []
    try:
        clean_spans = _collect_clean_spans(page_dict, page_w, page_h)
        for tab in page.find_tables().tables:
            cells = _rebuild_table_cells(tab, clean_spans) or tab.extract()
            tables.append(TableBlock(
                bbox=tab.bbox, page_num=page_idx,
                row_count=tab.row_count, col_count=tab.col_count,
                markdown=_cells_to_md(cells), cells=cells,
            ))
    except Exception as e:
        logging.warning(f"表格识别异常(页{page_idx}): {e}")
    return tables


# ──────────────────────────────── 目录识别 ────────────────────────────────

_TOC_TITLE_KW = re.compile(r'^[\s]*(目[\s]*录|contents|table[\s]*of[\s]*contents)[\s]*$', re.IGNORECASE)
_RE_TOC_LEADER = re.compile(r'[\.。…·\-\—\─\s]{3,}')
_RE_TOC_PAGE_NUM = re.compile(r'[\s\.。…·\-\—\─]+(\d{1,4})\s*$')

# 目录编号模式
_RE_TOC_NUM1 = re.compile(r'^[\s]*\d+[\.．、]\s*')
_RE_TOC_NUM2 = re.compile(r'^[\s]*\d+[\.．]\d+[\.．]\s*')
_RE_TOC_NUM3 = re.compile(r'^[\s]*\d+[\.．]\d+[\.．]\d+[\.．]\s*')


def _is_toc_page(page) -> bool:
    """判断页面是否为目录页"""
    lines = page.get_text("text").strip().split("\n")
    if any(_TOC_TITLE_KW.match(l.strip()) for l in lines[:5]):
        return True
    if sum(1 for l in lines if _RE_TOC_LEADER.search(l) and _RE_TOC_PAGE_NUM.search(l)) >= 3:
        return True
    return False



def detect_and_parse_toc(pdf_path: str) -> List[int]:
    """检测目录页并解析目录结构，返回 (条目列表, 目录页索引列表)"""
    doc = fitz.open(pdf_path)
    toc_indices = [i for i in range(min(doc.page_count, 10)) if _is_toc_page(doc.load_page(i))]
    doc.close()
    return toc_indices


# ──────────────────────────────── 标题识别 ────────────────────────────────

_RE_H1 = re.compile(r'^[\s]*\d+[\.．]\s*\S')
_RE_H2 = re.compile(r'^[\s]*\d+[\.．]\d+[\.．]\s*\S')
_RE_H3 = re.compile(r'^[\s]*\d+[\.．]\d+[\.．]\d+[\.．]\s*\S')
_RE_APPENDIX = re.compile(r'^[\s]*附[\s]*件[\s]*[\dA-Za-z一二三四五六七八九十]+[\.．、\s]?\s*\S')


def _heading_level(text: str) -> int:
    """从编号模式推断标题层级（1~4），0=不是标题编号"""
    if _RE_H3.match(text):
        return 3
    if _RE_H2.match(text):
        return 2
    if _RE_H1.match(text) or _RE_APPENDIX.match(text):
        return 1
    return 0


def _classify(text) -> str:
    """判断文本块的标题层级"""
    # 编号模式

    if _RE_H3.match(text): return "h3"
    if _RE_H2.match(text): return "h2"
    if _RE_APPENDIX.match(text) or _RE_H1.match(text): return "h1"
    return "text"


# ──────────────────────────────── 页脚页码去除 ────────────────────────────────

_RE_FOOTER_NUM = re.compile(r'^[\s\-—–·]*第?\s*\d{1,4}\s*页?[\s\-—–·]*$')


def _is_footer(text: str, bbox, page_h) -> bool:
    """判断文本块是否为页脚页码（底部15%区域 + 纯数字内容）"""
    y_mid = (bbox[1] + bbox[3]) / 2
    if y_mid < page_h * 0.85:
        return False
    t = text.strip()
    if _RE_FOOTER_NUM.match(t):
        return True
    # 单行数字
    if "\n" not in t:
        s = re.sub(r'^[-\s—–·]+', '', t)
        s = re.sub(r'[-\s—–·]+$', '', s)
        s = re.sub(r'^第\s*', '', s)
        s = re.sub(r'\s*页$', '', s)
        return bool(re.match(r'^\d{1,4}$', s.strip()))
    return False


# ──────────────────────────────── 核心提取 ────────────────────────────────

def extract_blocks_with_coords(
    pdf_path: str,
    toc_indices: Optional[List[int]] = None,
) -> List[PageInfo]:
    """
    提取 PDF 各页文本块 + 表格块

    - 倾斜水印丢弃
    - 页面外文字丢弃
    - 页脚页码去除
    - 表格内文本跳过（由表格 Markdown 替代）
    - 目录匹配 + 编号模式 + 字号加粗 分级标题
    """
    doc = fitz.open(pdf_path)
    toc_set = set(toc_indices or [])

    # 预提取每页表格
    table_map: Dict[int, List[TableBlock]] = {}
    for pi in range(doc.page_count):
        p = doc.load_page(pi)
        pd = p.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        pw, ph = p.rect.width, p.rect.height
        table_map[pi] = _extract_tables(p, pi, pd, pw, ph)

    pages: List[PageInfo] = []
    for pi in range(doc.page_count):
        p = doc.load_page(pi)
        pd = p.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        pw, ph = p.rect.width, p.rect.height
        is_toc = pi in toc_set

        page_info = PageInfo(page_num=pi, width=pw, height=ph,
                             tables=table_map[pi], is_toc_page=is_toc)

        # 提取文本块
        tbboxes = [t.bbox for t in page_info.tables]

        for block_idx, block in enumerate(pd.get("blocks", [])):
            if block.get("type") != 0:
                continue
            block_bbox = block.get("bbox", (0, 0, 0, 0))
            block_in_table = False
            if _block_center_in_table(block_bbox, tbboxes):
                block_in_table = True
            for line_idx, line in enumerate(block.get("lines", [])):
                if _is_line_tilted(line.get("dir", (1, 0))):
                    continue
                line_bbox = line.get("bbox", (0, 0, 0, 0))
                line_text = ""
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    span_text = span_text.rstrip()
                    if span_text:
                        # 去除页脚页码
                        if _is_footer(span_text, block_bbox, ph):
                            continue
                        line_text += span_text
                line_text = line_text.strip()
                if line_text and line_text not in {"，", "。"}:
                    btype = _classify(line_text)
                    if is_toc and btype in ("h1", "h2", "h3", "h4"):
                        btype = "toc_entry"

                    page_info.blocks.append(TextBlock(
                        text=line_text, bbox=line_bbox, page_num=pi,block_num=block_idx,
                        is_in_table= block_in_table,
                        block_type=btype, block_id=f"block_{pi}_{block_idx}_{line_idx}"
    ))

        pages.append(page_info)

    doc.close()
    return pages


# ──────────────────────────────── Markdown 生成 ────────────────────────────────

_H_MARKS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}


def generate_markdown(pages: List[PageInfo]) -> str:
    """生成 Markdown 文本"""
    md = []
    for pi in pages:
        # 按 y 坐标排序合并文本块和表格
        elems = sorted(
            [{"kind": "text", "y": (b.bbox[1]+b.bbox[3])/2, "d": b} for b in pi.blocks] +
            [{"kind": "table", "y": (t.bbox[1]+t.bbox[3])/2, "d": t} for t in pi.tables],
            key=lambda e: e["y"],
        )
        for e in elems:
            if e["kind"] == "table":
                md += ["", e["d"].markdown, ""]
            else:
                b = e["d"]
                t = b.text.strip()
                if not t:
                    continue
                if b.is_in_table:
                    continue
                if b.block_type == "toc_entry":
                    lvl = _heading_level(t) or 1
                    md.append("  " * (lvl - 1) + f"- {t}")
                elif b.block_type in _H_MARKS:
                    md += [f"{_H_MARKS[b.block_type]} {t}", ""]
                else:
                    md += [t, ""]
    return "\n".join(md)

# ──────────────────────────────── 主入口 ────────────────────────────────

def parse_text_pdf(pdf_path: str) -> PdfParseResult:
    """解析文本类型 PDF：目录 → 提取 → 标题识别 → Markdown"""
    toc_indices = detect_and_parse_toc(pdf_path)
    pages = extract_blocks_with_coords(pdf_path, toc_indices=toc_indices)
    return PdfParseResult(
        pdf_path=pdf_path,
        total_pages=len(pages),
        pages=pages,
        markdown=generate_markdown(pages))


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     pdf_path = r"/test_api/pytest/data/草台第一分散式电站电力监控系统二次安全防护实施方案.pdf"
#     result = parse_text_pdf(pdf_path)
#
#     print(f"总页数: {result.total_pages}")

