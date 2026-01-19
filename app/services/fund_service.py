"""Fund management service"""

from typing import Optional
from sqlalchemy.orm import Session
from app.models.fund import Fund
from app.core.sec_client import SECAPIClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class FundService:
    """Handles fund CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_all_funds(self, include_inactive: bool = True) -> list[Fund]:
        """Get all funds"""
        query = self.db.query(Fund)
        if not include_inactive:
            query = query.filter(Fund.is_active == True)
        return query.order_by(Fund.name, Fund.cik).all()

    def get_active_funds(self) -> list[Fund]:
        """Get only active funds"""
        return self.get_all_funds(include_inactive=False)

    def get_fund_by_id(self, fund_id: int) -> Optional[Fund]:
        """Get fund by ID"""
        return self.db.query(Fund).filter(Fund.id == fund_id).first()

    def get_fund_by_cik(self, cik: str) -> Optional[Fund]:
        """Get fund by CIK"""
        return self.db.query(Fund).filter(Fund.cik == cik).first()

    async def add_fund(self, cik: str) -> Fund:
        """
        Add a new fund by CIK.
        Attempts to look up the company name and ticker from SEC API.
        """
        # Clean CIK (remove leading zeros)
        cik_clean = cik.lstrip("0") or "0"

        # Check if already exists
        existing = self.get_fund_by_cik(cik_clean)
        if existing:
            if not existing.is_active:
                # Reactivate
                existing.is_active = True
                self.db.commit()
                return existing
            raise ValueError(f"Fund with CIK {cik_clean} already exists")

        # Try to get company info from SEC API
        name = None
        ticker = None
        try:
            async with SECAPIClient(settings.SEC_API_KEY) as client:
                info = await client.get_company_info(cik_clean)
                if info:
                    name = info.get("name")
                    ticker = info.get("ticker")
        except Exception as e:
            logger.warning(f"Could not fetch company info for CIK {cik_clean}: {e}")

        # Create fund
        fund = Fund(
            cik=cik_clean,
            name=name,
            ticker=ticker,
            is_active=True
        )
        self.db.add(fund)
        self.db.commit()
        self.db.refresh(fund)

        logger.info(f"Added fund: CIK={cik_clean}, name={name}, ticker={ticker}")
        return fund

    def update_fund(self, fund_id: int, name: str = None, ticker: str = None) -> Optional[Fund]:
        """Update fund details"""
        fund = self.get_fund_by_id(fund_id)
        if not fund:
            return None

        if name is not None:
            fund.name = name
        if ticker is not None:
            fund.ticker = ticker

        self.db.commit()
        self.db.refresh(fund)
        return fund

    def toggle_fund_status(self, fund_id: int) -> Optional[Fund]:
        """Toggle fund active/inactive status"""
        fund = self.get_fund_by_id(fund_id)
        if not fund:
            return None

        fund.is_active = not fund.is_active
        self.db.commit()
        self.db.refresh(fund)
        return fund

    def deactivate_fund(self, fund_id: int) -> bool:
        """Soft-delete a fund by deactivating it"""
        fund = self.get_fund_by_id(fund_id)
        if not fund:
            return False

        fund.is_active = False
        self.db.commit()
        return True

    def delete_fund(self, fund_id: int) -> bool:
        """Hard-delete a fund (use with caution - also deletes document records)"""
        fund = self.get_fund_by_id(fund_id)
        if not fund:
            return False

        self.db.delete(fund)
        self.db.commit()
        return True

    def get_fund_count(self, active_only: bool = True) -> int:
        """Get count of funds"""
        query = self.db.query(Fund)
        if active_only:
            query = query.filter(Fund.is_active == True)
        return query.count()
