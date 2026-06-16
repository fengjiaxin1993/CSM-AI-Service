"""
文件缓存工具 - OCR 结果以 contract_id 为维度存储到文件系统
目录结构: data/cache/{contract_id}/
    ├── locate.json        (OCR 定位结果)
    ├── markdown.md        (OCR Markdown 全文)
    └── structure.json     (结构化分块结果)
"""
import os
import json
from typing import Dict, Optional
from csm_ai_service.settings import Settings
from csm_ai_service.server.utils import build_logger
logger = build_logger()


def get_contract_cache_dir(contract_id: int) -> str:
    """获取合同 OCR 缓存目录路径"""
    cache_dir = os.path.join(Settings.basic_settings.CACHE_DATA_PATH, str(contract_id))
    return cache_dir


def ensure_cache_dir(contract_id: int) -> str:
    """确保合同缓存目录存在，返回路径"""
    cache_dir = get_contract_cache_dir(contract_id)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_cache_file_paths(contract_id: int) -> dict:
    """
    获取合同缓存文件的各路径

    Returns:
        {
            "locate_json": "data/cache/{contract_id}/locate.json",
            "markdown": "data/cache/{contract_id}/markdown.md",
            "structure_json": "data/cache/{contract_id}/structure.json",
        }
    """
    cache_dir = get_contract_cache_dir(contract_id)
    return {
        "locate_json": os.path.join(cache_dir, "locate.json"),
        "markdown": os.path.join(cache_dir, "markdown.md"),
        "structure_json": os.path.join(cache_dir, "structure.json"),
    }


def load_cached_ocr_result(contract_id: int) -> Optional[Dict]:
    """
    加载合同的 OCR 缓存结果

    Args:
        contract_id: 合同ID

    Returns:
        dict or None: {"locate_json_result", "markdown_text", "structure_json_result"}
    """
    paths = get_cache_file_paths(contract_id)
    locate_path = paths["locate_json"]
    md_path = paths["markdown"]
    structure_path = paths["structure_json"]

    if os.path.exists(locate_path) and os.path.exists(md_path) and os.path.exists(structure_path):
        try:
            with open(locate_path, 'r', encoding='utf-8') as f:
                locate_json_result = json.load(f)
            with open(md_path, 'r', encoding='utf-8') as f:
                markdown_text = f.read()
            with open(structure_path, 'r', encoding='utf-8') as f:
                structure_json_result = json.load(f)
            return {
                "locate_json_result": locate_json_result,
                "markdown_text": markdown_text,
                "structure_json_result": structure_json_result,
            }
        except Exception as e:
            logger.error(f"加载 OCR 缓存失败: {str(e)}")

    return None


def save_ocr_result(
    contract_id: int,
    locate_json_result: Dict,
    markdown_text: str,
    structure_json_result: Dict,
):
    """
    保存 OCR 结果到文件缓存

    Args:
        contract_id: 合同ID
        locate_json_result: OCR 定位 JSON 结果
        markdown_text: Markdown 全文
        structure_json_result: 结构化分块 JSON 结果
    """
    ensure_cache_dir(contract_id)
    paths = get_cache_file_paths(contract_id)

    try:
        with open(paths["locate_json"], 'w', encoding='utf-8') as f:
            json.dump(locate_json_result, f, ensure_ascii=False, indent=2)
        with open(paths["markdown"], 'w', encoding='utf-8') as f:
            f.write(markdown_text)
        with open(paths["structure_json"], 'w', encoding='utf-8') as f:
            json.dump(structure_json_result, f, ensure_ascii=False, indent=2)
        logger.info(f"OCR 结果已缓存: contract_id={contract_id}, dir={get_contract_cache_dir(contract_id)}")
    except Exception as e:
        logger.error(f"保存 OCR 缓存失败: {str(e)}")


def delete_ocr_cache(contract_id: int):
    """删除合同的 OCR 缓存目录"""
    import shutil
    cache_dir = get_contract_cache_dir(contract_id)
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            logger.info(f"已删除 OCR 缓存: contract_id={contract_id}, dir={cache_dir}")
        except Exception as e:
            logger.error(f"删除 OCR 缓存失败: {str(e)}")


def has_ocr_cache(contract_id: int) -> bool:
    """检查合同是否有 OCR 缓存"""
    paths = get_cache_file_paths(contract_id)
    return (
        os.path.exists(paths["locate_json"]) and
        os.path.exists(paths["markdown"]) and
        os.path.exists(paths["structure_json"])
    )
