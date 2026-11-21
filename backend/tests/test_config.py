"""後端設定載入與 Fail Fast 驗證單元測試。"""

import os
import unittest
from unittest.mock import patch

from config import AppConfig, DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES


class TestAppConfig(unittest.TestCase):
    """驗證 AppConfig 環境變數讀取與邊界檢查。"""

    def test_defaults_when_env_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            cfg = AppConfig.from_env()
            self.assertEqual(cfg.access_token_expire_minutes, DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)

    def test_invalid_non_positive_ttl_raises_value_error(self) -> None:
        with patch.dict(os.environ, {"SESSION_TTL_MINUTES": "0"}, clear=True):
            with self.assertRaises(ValueError):
                AppConfig.from_env()


if __name__ == "__main__":
    unittest.main()
