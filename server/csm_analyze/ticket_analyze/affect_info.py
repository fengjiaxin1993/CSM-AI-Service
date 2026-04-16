from fastapi import Body

from server.utils import BaseResponse

# 设备类型映射：英文标识 -> 中文名称
DEVICE_TYPE_MAP = {
    "security": "监测装置",
    "encryption": "纵向加密",
    "card": "加密卡",
    "firewall": "防火墙",
    "isolation": "横向隔离",
    "detection": "入侵检测",
    "malicious": "恶意代码",
    "gateway": "运维网关"
}


def get_device_types(maintenance_object: str, affected_object: str, work_content: str,
                     is_substation: bool = True) -> list:
    """
    根据输入的检修对象、影响对象和工作内容，返回设备类型列表。

    支持的设备类型：MONITORING_DEVICE(监测装置)、LONGITUDINAL_ENCRYPTION(纵向加密)

    规则：
    - 主站：检测到什么设备类型就返回什么，没有检测到的就不返回
    - 厂站：如果内容明确提到监测装置，则包含"监测装置"；如果提到纵向加密，则包含"纵向加密"；
           如果都没有提到，则返回所有支持的设备类型

    Args:
        maintenance_object: 检修对象
        affected_object: 影响对象
        work_content: 工作内容
        is_substation: 是否是厂站，默认是

    Returns:
        设备类型列表（英文标识）
    """
    # 合并所有输入内容进行判断
    all_content = f"{maintenance_object}{affected_object}{work_content}"

    device_types = []

    if is_substation:  # 厂站
        if DEVICE_TYPE_MAP["security"] in all_content:
            device_types.append("security")
        if DEVICE_TYPE_MAP["encryption"] in all_content:
            device_types.append("encryption")
        if len(device_types) == 0:
            device_types.append("security")
            device_types.append("encryption")
    else:  # 主站
        for k, v in DEVICE_TYPE_MAP.items():
            if v in all_content:
                device_types.append(k)
    return device_types


def associate_device_type(
        maintenance_object: str = Body("叶家河光储正向隔离装置", description="检修对象"),
        affected_object: str = Body("叶家河光储正向隔离装置", description="影响对象"),
        work_content: str = Body("需要重新配置叶家河光储正向隔离装置光功率预测相关策略", description="工作内容"),
        is_substation: bool = Body(True, description="是否未厂站")
) -> BaseResponse:
    device_types = get_device_types(maintenance_object, affected_object, work_content, is_substation)
    return BaseResponse(code=200, msg="设备类型判断成功", data=device_types)


if __name__ == "__main__":
    # 厂站测试用例
    print("=== 厂站测试 ===")
    print(get_device_types("监测装置A", "服务器", "更换设备", True))  # ['MONITORING_DEVICE']
    print(get_device_types("加密设备", "纵向加密装置", "维护", True))  # ['LONGITUDINAL_ENCRYPTION']
    print(get_device_types("监测装置", "纵向加密", "检修", True))  # ['MONITORING_DEVICE', 'LONGITUDINAL_ENCRYPTION']
    print(get_device_types("服务器", "数据库", "系统升级", True))  # ['MONITORING_DEVICE', 'LONGITUDINAL_ENCRYPTION']

    # 主站测试用例
    print("\n=== 主站测试 ===")
    print(get_device_types("监测装置A", "服务器", "更换设备", False))  # ['MONITORING_DEVICE']
    print(get_device_types("加密设备", "纵向加密装置", "维护", False))  # ['LONGITUDINAL_ENCRYPTION']
    print(get_device_types("监测装置", "纵向加密", "检修", False))  # ['MONITORING_DEVICE', 'LONGITUDINAL_ENCRYPTION']
    print(get_device_types("服务器", "数据库", "系统升级", False))  # []
