
def get_ocr() -> "RapidOCR":
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    return ocr
