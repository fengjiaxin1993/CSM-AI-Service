from PIL import Image
import numpy as np
from bs4 import BeautifulSoup
from rapid_doc import RapidDoc
from rapid_doc.model.layout.rapid_layout_self import ModelType as LayoutModelType
from rapidocr import ModelType as OCRModelType, OCRVersion, EngineType as OCREngineType
from rapid_doc.model.table.rapid_table_self import ModelType as TableModelType, EngineType as TableEngineType
import cv2
from typing import List
import numpy as np
from server.csm_analyze.warning_analysis.extract_info.helper import clean_text

_rapid_doc_engine: RapidDoc = None


def get_rapid_doc_engine() -> RapidDoc:
    """获取 RapidDoc 引擎实例（懒加载）"""
    global _rapid_doc_engine
    if _rapid_doc_engine is None:
        ocr_config = {
            "Det.model_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\ch_PP-OCRv5_mobile_det.onnx",
            "Rec.model_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\ch_PP-OCRv4_rec_mobile.onnx",
            "Cls.model_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\ch_ppocr_mobile_v2.0_cls_mobile.onnx",

            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Rec.ocr_version": OCRVersion.PPOCRV4,
            "Cls.ocr_version": OCRVersion.PPOCRV4,

            "Det.model_type": OCRModelType.MOBILE,
            "Rec.model_type": OCRModelType.MOBILE,
            "Cls.model_type": OCRModelType.MOBILE,

            # 强制使用 onnxruntime 引擎，避免 OpenVINO 路径问题
            "Det.engine_type": OCREngineType.ONNXRUNTIME,
            "Rec.engine_type": OCREngineType.ONNXRUNTIME,
            "Cls.engine_type": OCREngineType.ONNXRUNTIME,

            "Rec.rec_batch_num": 3,
            "Det.rec_batch_num": 3,
            "Cls.rec_batch_num": 3,

            "use_det_mode": 'auto',
            "seal_enable": False,  # 关闭印章识别，避免创建第二个 OCR 实例时下载模型
        }
        layout_config = {
            "model_type": LayoutModelType.PP_DOCLAYOUTV2,
            "conf_thresh": 0.1,
            "batch_num": 3,
            "model_dir_or_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\pp_doclayoutv2.onnx"
        }
        table_config = {
            "model_type": TableModelType.UNET_SLANET_PLUS,
            "model_dir_or_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\slanet-plus.onnx",
            "cls.model_type": TableModelType.PADDLE_Q_CLS,  # 表格分类模型
            "cls.model_dir_or_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\paddle_cls.onnx",  # 表格分类模型地址
            "unet.model_dir_or_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\unet.onnx",
            "slanet_plus.model_dir_or_path": r"D:\github\CSM-AI-Service\src\csm_ai_service\data\models\rapid_doc\slanet-plus.onnx",
            "engine_type": TableEngineType.ONNXRUNTIME,
        }
        image_config = {
            "extract_original_image": False,
            "extract_original_image_iou_thresh": 0.5
        }

        _rapid_doc_engine = RapidDoc(
            ocr_config=ocr_config,
            image_config=image_config,
            table_config=table_config,
            layout_config=layout_config,
            formula_enable=False,
            table_enable=True
        )
    return _rapid_doc_engine

def adapt_image_to_pil(image: np.ndarray) -> Image.Image:
    """将 List[np.ndarray] 转换为 List[PIL.Image]"""

    pil_img = Image.fromarray(image)
    return pil_img





def images_to_bytes_list(images: List[np.ndarray]) -> List[bytes]:
    """将 List[np.ndarray] 转换为 List[bytes]（PNG 格式）"""
    bytes_list = []
    for img in images:
        # np.ndarray 是 RGB，cv2 需要 BGR
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        _, encoded = cv2.imencode(".png", img_bgr)
        bytes_list.append(encoded.tobytes())
    return bytes_list


def html_table_to_info(html_table) -> dict:
    """
    把 RapidDoc 输出的 <table> 表格 转成 标准 Markdown 表格
    支持 rowspan / colspan 合并单元格
    """
    soup = BeautifulSoup(html_table, "html.parser")
    table = soup.find("table")
    if not table:
        return {}

    rows = table.find_all("tr")
    if len(rows) < 1:
        return {}

    # 处理跨行跨列核心逻辑
    row_span_map = []
    table_data = []

    for tr in rows:
        cells = tr.find_all(["td", "th"])
        current_row = []
        col_idx = 0

        # 填充跨行遗留单元格
        while col_idx < len(row_span_map) and row_span_map[col_idx] > 0:
            current_row.append(table_data[-1][col_idx])
            row_span_map[col_idx] -= 1
            col_idx += 1

        for cell in cells:
            text = cell.get_text(strip=True)
            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            # 处理跨列
            for _ in range(colspan):
                current_row.append(text)
                # 处理跨行
                if rowspan > 1:
                    while len(row_span_map) <= col_idx:
                        row_span_map.append(0)
                    row_span_map[col_idx] = rowspan - 1
                col_idx += 1

        table_data.append(current_row)

    # 生成标准 Markdown 表格
    table_info = {}
    if len(table_data) > 0:
        header_list = table_data[0]
        first_line = table_data[1]
        for i, header in enumerate(header_list):
            if i < len(first_line):
                table_info[clean_text(header)] = clean_text(first_line[i])
    return table_info
    md = []
    for i, row in enumerate(table_data):
        line = "| " + " | ".join(row) + " |"
        md.append(line)
        if i == 0:
            md.append("|" + "|".join(["---"] * len(row)) + "|")

    return "\n".join(md)



if __name__ == "__main__":
    file_path = r"/test_api/pytest/data/告警处置报告-demo-图片版.pdf"
    engine = get_rapid_doc_engine()

    # bytes_list = images_to_bytes_list(images)
    outputs = engine(inputs=file_path)
    print(outputs)

    # res = html_table_to_info("<table><tr><td rowspan=1 colspan=1>设备名称</td><td rowspan=1 colspan=1>设备类型</td><td rowspan=1 colspan=1>告警时间</td><td rowspan=1 colspan=1>告警内容</td></tr><tr><td rowspan=1 colspan=1>XXX监测装置</td><td rowspan=1 colspan=1>监测装置</td><td rowspan=1 colspan=1>2025-X-X X:X:X</td><td rowspan=1 colspan=1>由 综自 后台1 （XX） 拦截XXXX的<br>XX 端 口向 XXX 的 XX 端 口 之间 存在<br>XX端口访问</td></tr><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td></tr></table>")
    # print(res)