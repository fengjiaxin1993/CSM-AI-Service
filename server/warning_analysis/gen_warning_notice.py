import os
from fastapi import HTTPException

from server.utils import build_logger
from server.warning_analysis.convert_tools import generate_word_from_data, word2pdf, delete_pdf_text
from settings import Settings

logger = build_logger()

WARNING_TEMPLATE_NAME = "warning_notice_template.docx"

# 定义必选字段（与模板占位符一一对应）
REQUIRED_FIELDS = [
    "notice_no", "receive", "editor", "auditor",
    "warning_time", "warning_unit", "monitor_device", "warning_level",
    "latest_time", "device_ip", "content",
    "reason_analysis", "disposal_suggest",
    "deadline", "contact_tel", "cur_date"
]


def generate_pdf_from_data(data: dict) -> str:
    """
    内部函数：根据填充数据生成PDF，返回PDF临时文件路径
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
    word_name = suffix_name + ".docx"
    middle_name = suffix_name + "_temp.pdf"
    pdf_name = suffix_name + ".pdf"

    word_path = os.path.join(Settings.basic_settings.BASE_TEMP_DIR, word_name)
    middle_path = os.path.join(Settings.basic_settings.BASE_TEMP_DIR, middle_name)
    pdf_path = os.path.join(Settings.basic_settings.BASE_TEMP_DIR, pdf_name)
    for f in [word_path, middle_path, pdf_path]:
        if os.path.exists(f):
            os.remove(f)
    try:
        # 1.生成word文件
        generate_word_from_data(data, TEMPLATE_PATH, word_path)
        # 2.生成pdf(带水印)
        word2pdf(word_path, middle_path)
        # 3. 删除水印
        text_to_delete = "Evaluation Warning: The document was created with Spire.Doc for Python"
        delete_pdf_text(middle_path, pdf_path, text_to_delete)

        if not os.path.exists(pdf_path):
            raise Exception("PDF文件生成失败，未找到生成的文件")
        for f in [word_path, middle_path]:
            if os.path.exists(f):
                os.remove(f)
        return pdf_path

    except Exception as e:
        # 异常时清理临时文件
        for f in [word_path, middle_path]:
            if os.path.exists(f):
                os.remove(f)
        raise HTTPException(status_code=500, detail=f"PDF生成失败：{str(e)}")
