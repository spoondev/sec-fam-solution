from sqlalchemy import Column, String, DateTime
from datetime import datetime
from app.database import Base


class Setting(Base):
    """Key-value settings storage"""
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Setting(key={self.key})>"
