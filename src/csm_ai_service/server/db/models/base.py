from datetime import datetime

import pytz
from sqlalchemy import Column, DateTime, Integer, String
from zoneinfo import ZoneInfo


def get_shanghai_time():
    """获取上海时区的当前时间"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class BaseModel:
    """
    基础模型
    """

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(
        DateTime, default=None, onupdate=get_shanghai_time(), comment="更新时间"
    )
    create_by = Column(String, default=None, comment="创建者")
    update_by = Column(String, default=None, comment="更新者")
