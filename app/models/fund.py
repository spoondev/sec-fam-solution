from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Fund(Base):
    """Represents a fund to monitor for SEC filings"""
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, index=True)
    cik = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255))
    ticker = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="fund")

    def __repr__(self):
        return f"<Fund(cik={self.cik}, name={self.name})>"
