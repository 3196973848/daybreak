"""设置模型"""
from sqlalchemy import Boolean, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_time: Mapped[str] = mapped_column(String(5), default="08:00")  # HH:MM 格式
