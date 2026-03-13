# 目标：根据word的模板文件生成pdf文件
import fitz
from docxtpl import DocxTemplate
from spire.doc import *


# 根据word模板文件生成word文件
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


# 注意：Free Spire.Doc for Python 是一个免费的Word库，
# 免费版限制为 500 段落和 25 个表格。此限制在读取或写入 Word 文件时会被强制执行。
# 当将 Word 文档转换为 PDF 和 XPS 文件时，您只能获取前 3 页。
# 生成 pdf 文件还会出现 红色字体水印 https://www.e-iceblue.cn/Introduce/Free-Spire-Doc-Python.html
def word2pdf(word_path, pdf_path):
    # 创建 Document 类的对象
    document = Document()

    # 加载一个 .doc 或 .docx 文档
    document.LoadFromFile(word_path)

    # 将文档保存为PDF格式
    document.SaveToFile(pdf_path, FileFormat.PDF)
    document.Close()


# 在pdf找出关键字的bbox信息
def get_pdf_bbox(input_pdf, text_to_find):
    doc = fitz.open(input_pdf)
    page = doc[0]
    res = None
    for block in page.get_text("dict")["blocks"]:
        if block["type"] == 0:
            for line in block["lines"]:
                for span in line["spans"]:
                    if text_to_find in span["text"]:
                        res =  span["bbox"]
                        break
    doc.close()
    return res


# 删除pdf中的水印
def delete_pdf_text(input_pdf, output_pdf, text_to_delete):
    bbox = get_pdf_bbox(input_pdf, text_to_delete)
    if bbox is None:
        return
    doc = fitz.open(input_pdf)
    page = doc[0]
    rect = fitz.Rect(bbox)
    page.add_redact_annot(rect, fill=(1, 1, 1))  # 白色覆盖
    page.apply_redactions()  # 真正删除

    doc.save(output_pdf)
    doc.close()
