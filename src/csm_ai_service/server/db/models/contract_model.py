from sqlalchemy import Column, String, DateTime, Integer
from csm_ai_service.server.db.base import Base
from csm_ai_service.server.db.models.base import get_shanghai_time


class ContractModel(Base):
    """
    合同模型 - 存储上传的合同文件元信息
    数据库不存储任何路径信息，只存储文件名称。
    路径通过 os.path.join 动态拼接：
      - 上传文件: data/uploads/{file_name}
      - OCR 缓存: data/cache/{contract_id}/
    """
    __tablename__ = "contract"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="合同唯一ID")
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    file_type = Column(String(50), default="pdf", comment="文件类型")

    # 处理状态
    status = Column(String(20), default="pending", comment="处理状态: pending/processing/completed/failed")
    create_time = Column(DateTime, default=get_shanghai_time(), comment="创建时间")
    update_time = Column(DateTime, default=get_shanghai_time(), onupdate=get_shanghai_time(), comment="更新时间")

    def __repr__(self):
        return f"<Contract(id={self.id}, file_name='{self.file_name}', status='{self.status}')>"
