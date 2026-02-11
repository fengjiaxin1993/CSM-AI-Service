import os
import tempfile
from docxtpl import DocxTemplate  # 增强版模板填充，适配表格/多段文本
from docx2pdf import convert
from datetime import datetime

from fastapi import HTTPException

from server.utils import build_logger

logger = build_logger()

# 配置Word模板路径（修改为你的实际模板路径）

# new_file_path = os.path.join(Settings.basic_settings.BASE_TEMP_DIR, file.filename)
TEMPLATE_PATH = r"D:\github\CSM-AI-Service\data\template_file\warning_notice_template.docx"
temp_word_path = r"D:\github\CSM-AI-Service\server\warning_analysis\temp.docx"
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
    try:
        # 4. 加载模板并填充数据
        tpl = DocxTemplate(TEMPLATE_PATH)
        # 关键优化1：将多行文本的\n转换为Word的换行符（<w:br/>），避免手动换行导致格式错乱
        for key, value in data.items():
            if isinstance(value, str) and "\n" in value:
                data[key] = value.replace("\n", "<br/>")
        # 关键优化2：使用RichText渲染，保留原模板的段落/单元格样式
        tpl.render(data, autoescape=False)
        tpl.save(temp_word_path)

        # 5. 跨平台转换为PDF（docx2pdf自动适配系统）
        # convert(temp_word_path, temp_pdf_path)

        # 6. 校验PDF是否生成成功
        if not os.path.exists(temp_word_path):
            raise Exception("PDF文件生成失败，未找到生成的文件")

        return temp_word_path

    except Exception as e:
        # 异常时清理临时文件
        # for f in [temp_word_path, temp_pdf_path]:
        #     if os.path.exists(f):
        #         os.remove(f)
        raise HTTPException(status_code=500, detail=f"PDF生成失败：{str(e)}")


# ------------------- 示例：填充数据 + 运行生成 -------------------
if __name__ == "__main__":
    fill_data = {
        "notice_no": "WLAQ2026021001",  # 通知单编号
        "receive": "湖北宜昌地调",  # 接收单位
        "editor": "张三岁",  # 编制人
        "auditor": "李四岁",  # 审核人
        "warning_time": "2026年02月03日",  # 告警接收时间
        "warning_unit": "宜昌地调网安平台东流溪二级水电站",  #告警产生单位
        "monitor_device": "监测装置",  # 设备名称
        "warning_level": "紧急",  #告警级别名称
        "latest_time": "2026-02-03 14:28:36",  # 告警最新发生时间
        "device_ip": "192.168.100.23",  # 告警设备IP
        "content": "电力监控系统终端存在未授权访问风险",  # 告警核心内容
        "reason_analysis": "现场运维人员安全意识不足，未严格执行《电力监控系统网络安全管理规定》，终端配置未做安全加固",
        # 原因分析
        "disposal_suggest": "1. 立即关闭默认高危端口3389；\n2. 修改管理员为强密码（8位以上字母+数字+特殊符号）；\n3. 开启终端日志审计并配置远程上报；\n4. 对运维人员开展网络安全专项培训",
        # 处置建议
        "deadline": "2026年02月20日",  # 整改截止日期
        "contact_tel": "027-8866XXXX",  # 省调联系电话
        "cur_date": datetime.now().strftime("%Y年%m月%d日")  # 通知单发布日期
    }
    pdf_path = generate_pdf_from_data(fill_data)
    print(pdf_path)
