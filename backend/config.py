"""後端參數與設定模組：集中管理環境變數、安全常數與目錄路徑。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

JWT_ALGORITHM = "HS256"
DEFAULT_JWT_SECRET = "dev-insecure-secret-change-me"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
DEFAULT_QR_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_SESSION_TTL_MINUTES = 15
SESSION_CLEANUP_INTERVAL_SECONDS = 60
DEFAULT_DEMO_USERNAME = "user1"


@dataclass(frozen=True)
class AppConfig:
    """不可變應用程式設定，統一透過環境變數注入。"""

    jwt_secret_key: str
    jwt_algorithm: str = JWT_ALGORITHM
    access_token_expire_minutes: int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    qr_token_expire_minutes: int = DEFAULT_QR_TOKEN_EXPIRE_MINUTES
    session_ttl_minutes: int = DEFAULT_SESSION_TTL_MINUTES

    @classmethod
    def from_env(cls) -> "AppConfig":
        """從環境變數載入設定並檢核數值範圍。"""
        access_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES))
        )
        session_ttl = int(
            os.getenv("SESSION_TTL_MINUTES", str(DEFAULT_SESSION_TTL_MINUTES))
        )
        if access_minutes <= 0 or session_ttl <= 0:
            raise ValueError("Token 與 Session 有效分鐘數必須大於 0")

        return cls(
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET),
            access_token_expire_minutes=access_minutes,
            session_ttl_minutes=session_ttl,
        )
