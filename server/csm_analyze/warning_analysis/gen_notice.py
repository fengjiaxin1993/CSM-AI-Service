import os
from fastapi import HTTPException
from fastapi.responses import FileResponse
from utils import build_logger
from settings import Settings
# 目标：根据word的模板文件生成word文件
from docxtpl import DocxTemplate
from cryptography.hazmat.primitives import hashes

logger = build_logger()
# 生成整改通知单


WARNING_TEMPLATE_NAME = "warning_notice_template.docx"

# 定义必选字段（与模板占位符一一对应）
REQUIRED_FIELDS = [
    "notice_no", "receive", "editor", "auditor",
    "warning_time", "warning_unit", "monitor_device", "warning_level",
    "latest_time", "device_ip", "content",
    "reason_analysis", "disposal_suggest",
    "deadline", "contact_tel", "cur_date"
]


def sm3_hash_file(file_path: str) -> str:
    h = hashes.Hash(hashes.SM3())
    with open(file_path, "rb") as f:
        h.update(f.read())
    return h.finalize().hex()


def generate_word_from_data(data: dict, template_path: str, word_path: str):
    """
    内部函数：根据填充数据生成word，返回word文件路径
    """
    # 1. 加载模板并填充数据
    tpl = DocxTemplate(template_path)
    # 关键优化1：将多行文本的\n转换为Word的换行符（<w:br/>），避免手动换行导致格式错乱
    for key, value in data.items():
        if isinstance(value, str) and "\n" in value:
            data[key] = value.replace("\n", "<br/>")
    # 关键优化2：使用RichText渲染，保留原模板的段落/单元格样式
    tpl.render(data, autoescape=False)
    tpl.save(word_path)
    return word_path


def generate_doc_from_data(data: dict):
    """
    内部函数：根据填充数据生成docx，返回docx临时文件路径
    """
    TEMPLATE_PATH = os.path.join(Settings.basic_settings.TEMPLATE_PATH, WARNING_TEMPLATE_NAME)
    # 1. 校验模板文件是否存在
    if not os.path.exists(TEMPLATE_PATH):
        raise HTTPException(status_code=500, detail=f"模板文件不存在，路径：{TEMPLATE_PATH}")

    # 2. 校验必选字段
    missing_fields = [f for f in REQUIRED_FIELDS if f not in data or not data[f]]
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"缺失必选字段/字段值为空：{','.join(missing_fields)}"
        )

    suffix_name = f"整改通知单-{data['notice_no']}"
    doc_name = suffix_name + ".docx"
    doc_path = os.path.join(Settings.basic_settings.WARNING_NOTICE_DIR, doc_name)

    if os.path.exists(doc_path):
        os.remove(doc_path)
    try:
        # 1.生成word文件
        generate_word_from_data(data, TEMPLATE_PATH, doc_path)
        # 2. 检查文件是否生成成功
        if not os.path.exists(doc_path):
            raise HTTPException(status_code=500, detail=f"{doc_name} 生成失败!!")
        # 3. 计算文件的sm3 hash值
        sm3_hash = sm3_hash_file(doc_path)
        # 4. 返回文件流（二进制流），并在响应头携带 SM3
        return FileResponse(
            path=doc_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=doc_name,
            headers={"X-SM3-HASH": sm3_hash}  # SM3 摘要在这里！
        )

    except Exception as e:
        if os.path.exists(doc_path):
            os.remove(doc_path)
        raise HTTPException(status_code=500, detail=f"{doc_name} 生成失败!!{str(e)}")
