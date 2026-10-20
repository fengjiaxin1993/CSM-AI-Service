import os
from fastapi import HTTPException
from fastapi.responses import FileResponse
from csm_ai_service.utils import build_logger
from csm_ai_service.settings import Settings
# 目标：根据word的模板文件生成word文件
from docxtpl import DocxTemplate

logger = build_logger()
# 生成整改通知单


WARNING_TEMPLATE_NAME = "warning_notice_template.docx"

# 定义必选字段（与模板占位符一一对应）
REQUIRED_FIELDS = [
    "notice_no", "receive", "editor", "auditor",
    "warning_time", "warning_unit", "monitor_device", "warning_level",
    "latest_time", "device_ip", "content",
    "rectification_requirements", "cur_date"
]


def generate_word_from_data(data: dict, template_path: str, word_path: str):
    """
    内部函数：根据填充数据生成word，返回word文件路径
    """
    # 1. 加载模板并填充数据
    tpl = DocxTemplate(template_path)
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
        # 4. 返回文件流（二进制流），并在响应头携带 SM3
        return FileResponse(
            path=doc_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=doc_name,
        )

    except Exception as e:
        if os.path.exists(doc_path):
            os.remove(doc_path)
        raise HTTPException(status_code=500, detail=f"{doc_name} 生成失败!!{str(e)}")
