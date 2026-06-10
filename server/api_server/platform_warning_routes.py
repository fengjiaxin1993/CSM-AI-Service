from __future__ import annotations
from fastapi import APIRouter, Body
from fastapi.responses import FileResponse

from utils import build_logger
from server.csm_analyze.warning_analysis.gen_notice import generate_doc_from_data
from server.csm_analyze.warning_analysis.report_analyze import warning_analyze, save_warning_report, delete_warning_report

logger = build_logger()

platform_warning_router = APIRouter(prefix="/warning_handle", tags=["模拟平台接口"])



@platform_warning_router.post("/warning",summary="告警分析")
# 一次性返回研判结果
def warning_analyze(data: dict = Body(
            ...,
            description="告警参数",
            example={
              "IP": "40.101.37.2",
              "destinationIp": "未知设备",
              "alertLevel": "紧急",
              "deviceType": "7",
              "logType": "2",
              "logSubType": "7",
              "alertStartTime": "2025/12/10 13:32",
              "currentAlertTime": "2025/12/10 13:32",
              "alertCount": "10",
              "alertStatusFlag": "0",
              "alertDescription": "未知设备(40.101.37.2)正在对实时业务未知设备(40.100.157.1, 40.100.157.2)等主机(51640, 51674, 51724, 35206, 51758,...)等端口进行端口扫描",
              "eventType": "0",
              "assetName": "未知设备",
              "assetId": "",
              "assetSubType": "服务器",
              "assetRegion": "01119901030000004",
              "alertType": "105",
              "alertSubType": "22",
              "newAlertCode": "SVR105022",
              "reportingDeviceType": "6",
              "regionName": "0021990103",
              "alertUniqueId": "344632032224759600",
              "regulationCloudId": "01119901030000004",
              "alertSource": "1001",
              "reportingDevice": "华中网调_湖南新一代集控站_I区_华中网调二次安全防护系统",
              "wmac": "9256668770066516552"
            }
        )) -> dict:
    res = {"code": "0",
           "msg": {
               "reason": "1、正常运维操作，例如远程管理或维护。\n2、自动化脚本执行，用于定期系统检查或数据同步。\n3、安全扫描或漏洞检测工具的使用，导致SSH端口被记录为访问行为。\n4、外部入侵者尝试通过SSH进行未授权访问。",
               "suggestion": "处置过程：1）确认该操作是否属于正常运维行为。如果是，则无需采取进一步措施；如果不是，请立即执行以下步骤。\n2）对涉及的两台工作站进行全面的安全检查，包括系统日志和网络流量分析。\n3）如果发现异常活动，请关闭SSH服务，并通知安全团队进行深入调查。\n整改情况：1）若为正常运维操作，则优化探针配置以避免此类告警重复上送。\n2）对于非运维操作导致的访问记录，需修复或加固相关系统设置，防止未授权访问。\n防范措施：1、实施最小化权限原则和严格的访问控制策略。\n2、定期更新操作系统和应用程序的安全补丁。\n3、加强对SSH服务使用的管理和监控。\n4、培训所有用户关于安全意识的重要性，包括如何识别和报告可疑活动。"
           },
           "result": "失败原因"
           }
    return res
