# -*- coding: utf-8 -*-
import json
from typing import Dict

from langchain_core.prompts import ChatPromptTemplate

from server.chat.utils import History
from server.csm_analyze.warning_analysis.extract_info.scanPdfExtractText import SCANPDFExtractText
from server.utils import get_ChatOpenAI, get_default_llm, get_prompt_template
from server.csm_analyze.warning_analysis.extract_info.helper import fix_llm_json_output
from server.csm_analyze.warning_analysis.extract_info.pdfExtractText import PDFExtractText
from server.csm_analyze.warning_analysis.extract_info.wordExtractText import WORDExtractText
from settings import Settings
from server.utils import build_logger

logger = build_logger()


def extract_structured_data(full_text: str,
                            table_data: str = "") -> Dict:
    """
    调用大模型从Word文档中提取结构化数据

    Args:
        full_text: Word文档的段落文本内容
        table_data: Word文档的表格数据（列表的列表，包含字典）

    Returns:
        解析后的结构化数据字典
    """

    model = get_default_llm()
    llm = get_ChatOpenAI(
        model_name=model,
        temperature=0.1,
        max_tokens=Settings.model_settings.MAX_TOKENS,
    )

    prompt_template = get_prompt_template("warning", "extract")
    # 渲染提示词
    input_msg = History(role="user", content=prompt_template).to_msg_template(False)
    chat_prompt = ChatPromptTemplate.from_messages([input_msg])
    prompt = chat_prompt.invoke({"full_text": full_text, "table_data": table_data})
    # x = prompt.to_string()
    response = llm.invoke(prompt)  # 一次性调用模型，返回完整响应

    content = response.content  # 核心：提取完整回答文本
    logger.info(f"抽取告警处置报告的大模型content:\n {content}")

    result = fix_llm_json_output(content)
    return result


def extract_text_from_file(file_path: str, ext: str) -> tuple[str, str]:
    if ext == ".docx":
        parser = WORDExtractText(file_path)
        full_text = parser.full_text
        table_data_text = str(parser.tables_data)
        return full_text, table_data_text
    elif ext == ".pdf":
        parser = PDFExtractText(file_path)
        full_text = parser.full_text
        table_data_text = str(parser.tables_data)
        if len(full_text) <= 50:  # 50个字都没有，使用ocr识别
            parser = SCANPDFExtractText(file_path)
            full_text = parser.full_text
            table_data_text = str(parser.table_data)
        return full_text, table_data_text


def extract_dict_from_file_by_llm(file_path: str, ext: str) -> Dict:
    full_text, table_data_text = extract_text_from_file(file_path, ext)
    # logger.info(f"full_text:\n {full_text[:100]}, \ntable_data_text: {table_data_text}")
    return extract_structured_data(full_text, table_data_text)


# ---------------------- 测试代码 ----------------------
if __name__ == "__main__":
    # 测试数据
    test_full_text = """A二级电站网络安全事件
调查报告
、事件基本情况(一)事件概况
2026年02月03日12时54分，地调网络安全检测平台系统告警显示35KVA二
级水电站综自后主机1（192.168.0.100）服务器接入无线网卡或手机设备，设备厂商：Logitech的紧急告警，随后告警信息同步上传至省调网络安全监视平台。经与现场核查确认，因后台主机1的有线鼠标出现问题，A二级电站值班员工插入了无线鼠标使用，引起报警。违反了《电力监控系统安全防护规定》(2025版)第	十三条：“生产控制区应当具有高安全性和高可靠性，禁止采用安全风险	高的通用网络服务功能，禁止选用具有无线通信功能的产品，应当对外设接入行为进行管控”。可能造成数据泄露或病毒感染。
(二)运行情况
A二级电站于2007年投运，2025年4月地调下发的网络安全隐患通知单，要求
部署网络安全监测装置，同年9月，完成网络安全监测装置接入工作，接入资产包括后台监控工作站1/2、数据网交换机、防火墙等并与主站完成网安告警测试。
(三)事件应急处置情况
A二级电站在收到Y地调自动化值班员电话后，立即启动应急处置程序，严格按照相关规范开展处置工作：一是第一时间拔出违规接入的无线鼠标，断开监控工作站与站控层交换机的连接，切断安全风险传播路径；二是停止日常工作，安排更换有线鼠标。三是对现场违章人员进行口头教育并通知全站人员参加安全专题会议，深入学习《电力监控系统安全防护规定》等相关文件。
二、事件原因分析
经全面复盘核查，本次网安告警事件的原因主要包括以下三个层面：
（一）直接原因
站内员工C对电力监控系统安全防护相关规定掌握不扎实，存在严重认知偏差，2025年9月份安装相关探针后未认证履行相关安全防护规定，意识还停留在之前老
上，对接入探针后的安全认知不足。
（二）间接原因
责任单位D安全管理体系落实不到位：未严格履行《电力监控系统安全防护规定》（国家发展改革委2024年第27号令）中“运营者是电力监控系统安全防护的责任主体，其主要负责人对电力监控系统安全防护负总责”的要求，对现场员工的安全培训流于形式，未确保人员熟练掌握《中华人民共和国数据安全法》《网络数据安全管理条例》等相关法律法规及作业规范。
（三）根本原因
责任单位及相关人员的网络安全意识和责任意识淡薄，未深刻认识到电力监控系统作为关键信息基础设施的安全重要性，即便责任单位已经签过《并网电厂网络监控系统安全责任书》，也未对里面内容落实到位，对核心条款第二条“生产控制大区内严禁使用任何具有无线功能模块的设备，包括但不限于无线鼠标、无线键盘、蓝牙设备、无线网卡”等条款重大安全隐患重视不足，未将数据安全、网络安全要求贯穿于日常维护工作的全流程，安全管理存在“应付”的倾向。
三、事件性质认定
依据《电力监控系统防护规定》、《国家电网有限公司安全事故调查规程》等文件对事件性质进行认定，本次事件违反了《电力监控系统防护规定》第十三条：生产控制区应当具有高安全性和高可靠性，禁止采用安全风险高的通用网络服务功能，禁止选用具有无线通信功能的产品，应当对外设接入行为进行管控。本次事件性质为D公司安全管理不到位、员工违规操作引发的重大网络安全隐患事件。
该事件中，站内员工擅自接入无线鼠标行为，属于《电力监控系统安全防护规定》（国家发展改革委2024年第27号令）明确的重大安全隐患范畴，违反了“生产控制大区内严禁使用任何具有无线功能模块的设备”的强制性要求，同时违背了数据安全保护、网络安全管理的相关法律法规，对电力监控系统安全和电网稳定运行构成严重威胁。
四、事件暴露的主要问题
（一）责任落实不到位
责任单位未严格履行电力监控系统安全防护主体责任，主要负责人未切实承担安全防护总责，未建立“全员、全流程、全方位”的安全责任体系，导致安全管理要求未能有效传递至一线作业人员。
（二）员工意识薄弱
员工对《网络数据安全管理条例》《电力监控系统安全防护规定》等相关法律法规和制度规范学习不深入，对非授权设备接入的严重危害认识不足，合规操作能力欠缺。
五、整改措施
（一）压实安全主体责任
D公司作为责任单位，其主要负责人需牵头组织全面整改工作，签订《网络安全责任承诺书》，明确各层级安全责任，将电力监控系统安全防护要求纳入公司核心管理制度，确保责任落实到人。
组织召开专题会议，深入学习《电力监控系统安全防护规定》（国家发展改革委2024年第27号令）等相关文件，深刻领会“运营者是安全防护责任主体”的要求，树立“安全第一
、预防为主”的理念。
（二）强化人员教育培训
责任单位需在收到整改通知之日起3个工作日内，组织现场全部调试人员开展专项培训，培训内容涵盖《网络数据安全管理条例》《电力监控系统安全防护规定》等作业规范
，配套开展告警应急处置演练。培训后组织闭卷考核，考核不合格者不得上岗作业。
建立常态化培训机制，每半年至少开展1次网络安全专项培训，每年组织1次应急演练，持续提升人员的安全意识、合规操作能力和应急处置水平，并将培训考核结果与绩效考核挂钩。
（三）规范作业全流程管理
严格执行“作业票开具-报备挂牌-调试实施-结束反馈”全流程管控要求，调试工作前必须完成作业票审批，主动致电网安及电网相关部门履行报备及挂牌手续，待确认后方可启动调试；每日调试结束后，及时反馈当日作业情况，形成闭环管理。
建立核心设备接入审批制度，任何外部设备接入电力监控系统相关设备前，必须提交书面申请，说明设备类型、用途、安全检测情况等，经网安及电网相关部门审核批准后
，在专人监督下进行接入操作，全程记录备案。
（四）完善安全管控机制
责任单位需在30个工作日内修订完善网络安全管理制度、作业操作规程和应急处置预案及建立常态化安全隐患排查机制，全面开展安全隐患排查，建立隐患台账，明确整改责任人和整改时限，实行闭环管理。
（五）强化监督考核
将网络安全工作纳入责任单位及相关人员的绩效考核体系，加大安全指标权重，对合规操作、隐患排查到位的给予奖励，对违规操作、整改落实不力的严肃追责。
电网相关部门定期对责任单位的整改落实情况进行复查，跟踪验证整改效果，对整改不到位、问题反弹的，采取加重处罚、暂停调试资格等措施，确保整改工作取得实效。
六、对有关责任人员和责任单位的处理
依据《中华人民共和国数据安全法》《电力监控系统安全防护规定》（国家发展改革委2024年第27号令）（国家电网安监〔2020〕820号）等相关规定，经研究决定，对事件相关责任人员及单位作出如下处理：
（一）对有关责任人的处理
.D公司员工C：予以公司内部通报批评，为严肃纪律杜绝此类违规行为再次发生，依据公司相关规章制度处以人民币3000元的罚款，从当月工资扣
除；公司组织相关培训，确保深刻认识自身违规行为的严重性，熟练掌握合规操作流程。
对D公司安全生产负责人E：予以通报批评，扣除当月30绩效奖金；责令牵头组织整改工作，向Y地调提交专项整改报告。
（二）对相关单位的处理
D公司：予以正式警告，责令立即全面落实整改措施，并在收到本报告之日起15个工作日内提交书面整改报告及验证材料。
七、附件
系统告警记录、终端操作日志
图1：网安告警详情
事件现场取证照片与整改完成照片
图2：已坏的有线鼠标	图3：违规使用的无线鼠标
图4：监控工作站背面整改后	图5：更换PS/2接口有线鼠标
图6：监控主机整改前USB接口	图7：监控主机USB封堵后照片
图8：禁止标示1-2
图8：站内安防及数据网设备封堵后照片
图9：网安专责对A二级相关人员进行安全教育
事件通报与处罚文件
网络安全培训材料、签到表与考核记录
相关管理制度文件、网络安全保密协议复印件
下发杜绝无线设备违规接入生产控制大区的通知"""

    test_table_data = ""

    result = extract_structured_data(test_full_text, test_table_data)
    print("=== 提取结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
