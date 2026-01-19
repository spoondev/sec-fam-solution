"""Settings management service"""

from typing import Optional
from sqlalchemy.orm import Session
from app.models.setting import Setting
from app.config import settings as app_settings
import logging

logger = logging.getLogger(__name__)


class SettingsService:
    """Handles application settings storage and retrieval"""

    # Default values for settings
    DEFAULTS = {
        "document_save_path": app_settings.DOCUMENT_SAVE_PATH,
        "scan_day_of_week": str(app_settings.SCAN_DAY_OF_WEEK),
        "scan_hour": str(app_settings.SCAN_HOUR),
        "scan_minute": str(app_settings.SCAN_MINUTE),
    }

    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value"""
        setting = self.db.query(Setting).filter(Setting.key == key).first()
        if setting:
            return setting.value

        # Return from defaults if not in DB
        if key in self.DEFAULTS:
            return self.DEFAULTS[key]

        return default

    def set(self, key: str, value: str) -> Setting:
        """Set a setting value"""
        setting = self.db.query(Setting).filter(Setting.key == key).first()

        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            self.db.add(setting)

        self.db.commit()
        self.db.refresh(setting)

        logger.info(f"Setting updated: {key}={value}")
        return setting

    def get_all(self) -> dict[str, str]:
        """Get all settings as a dictionary"""
        result = dict(self.DEFAULTS)  # Start with defaults

        # Override with DB values
        settings = self.db.query(Setting).all()
        for setting in settings:
            result[setting.key] = setting.value

        return result

    def get_document_save_path(self) -> str:
        """Get the document save path setting"""
        return self.get("document_save_path", app_settings.DOCUMENT_SAVE_PATH)

    def get_schedule_config(self) -> dict:
        """Get scheduler configuration"""
        return {
            "day_of_week": int(self.get("scan_day_of_week", "6")),
            "hour": int(self.get("scan_hour", "2")),
            "minute": int(self.get("scan_minute", "0")),
        }
