from __future__ import annotations
from fastapi import APIRouter

from utils import build_logger
from server.csm_analyze.ticket_analyze.affect_info import associate_device_type

logger = build_logger()

ticket_router = APIRouter(prefix="/ticket", tags=["检修票关联"])

ticket_router.post(
    "/associate_device",
    summary="根据票面内容，判断关联的设备类型(纵向加密、监测装置)",
)(associate_device_type)
