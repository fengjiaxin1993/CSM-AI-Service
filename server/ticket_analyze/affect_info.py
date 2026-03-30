from fastapi import Body

from server.utils import BaseResponse


def get_device_types(maintenance_object: str, affected_object: str, work_content: str) -> list:
    """
    根据输入的检修对象、影响对象和工作内容，返回设备类型列表。
    
    规则：
    - 如果内容明确提到监测装置，则包含"监测装置"
    - 如果内容明确提到纵向加密，则包含"纵向加密"
    - 如果都没有提到，则返回两个设备类型
    
    Args:
        maintenance_object: 检修对象
        affected_object: 影响对象
        work_content: 工作内容
        
    Returns:
        设备类型列表
    """
    # 合并所有输入内容进行判断
    all_content = f"{maintenance_object}{affected_object}{work_content}"

    device_types = []

    # 检查是否提到监测装置
    has_monitoring_device = "监测装置" in all_content

    # 检查是否提到纵向加密
    has_longitudinal_encryption = "纵向加密" in all_content

    if has_monitoring_device or has_longitudinal_encryption:
        # 如果有明确提到，则只列出提到的设备
        if has_monitoring_device:
            device_types.append("监测装置")
        if has_longitudinal_encryption:
            device_types.append("纵向加密")
    else:
        # 如果没有提到，则列出两个
        device_types = ["监测装置", "纵向加密"]

    return device_types


def associate_device_type(
        maintenance_object: str = Body("叶家河光储正向隔离装置",description="检修对象"),
        affected_object: str = Body("叶家河光储正向隔离装置",description="影响对象"),
        work_content: str = Body("需要重新配置叶家河光储正向隔离装置光功率预测相关策略",description="工作内容")
    ) -> BaseResponse:
    device_types = get_device_types(maintenance_object, affected_object, work_content)
    return BaseResponse(code=200, msg="设备类型判断成功", data=device_types)




if __name__ == "__main__":
    # 测试用例
    print(get_device_types("监测装置A", "服务器", "更换设备"))  # ['监测装置']
    print(get_device_types("加密设备", "纵向加密装置", "维护"))  # ['纵向加密']
    print(get_device_types("监测装置", "纵向加密", "检修"))  # ['监测装置', '纵向加密']
    print(get_device_types("服务器", "数据库", "系统升级"))  # ['监测装置', '纵向加密']
