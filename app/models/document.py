from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Document(Base):
    """Represents a retrieved SEC filing document"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False)
    accession_number = Column(String(25), unique=True, nullable=False, index=True)
    form_type = Column(String(20), nullable=False)
    filed_at = Column(DateTime, nullable=False, index=True)
    reporting_period_end = Column(Date)
    document_url = Column(String(500))
    local_filename = Column(String(255))
    local_path = Column(String(500))
    file_size_bytes = Column(Integer)
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    # Stretch goal: extracted fund metrics
    total_assets = Column(Float)
    shares_outstanding = Column(Integer)
    nav_per_share = Column(Float)

    fund = relationship("Fund", back_populates="documents")

    def __repr__(self):
        return f"<Document(accession={self.accession_number}, form={self.form_type})>"
