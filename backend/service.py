"""核心業務邏輯模組：管理 QR 登入會話、JWT 簽發驗證與貼文留言狀態。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Dict, List, Optional
import uuid

import jwt
import qrcode
from pydantic import BaseModel, Field

try:
    from backend.config import AppConfig, DEFAULT_DEMO_USERNAME
except ModuleNotFoundError:
    from config import AppConfig, DEFAULT_DEMO_USERNAME


# ---------------------------------------------------------------------------
# API 資料模型（Pydantic）
# ---------------------------------------------------------------------------
class Comment(BaseModel):
    """單則留言模型。"""

    id: int
    username: str
    content: str
    timestamp: str


class CommentCreate(BaseModel):
    """建立留言請求模型。"""

    content: str = Field(..., min_length=1, max_length=500)


class Post(BaseModel):
    """單篇貼文模型（含留言清單）。"""

    id: int
    username: str
    content: str
    timestamp: str
    comments: List[Comment] = Field(default_factory=list)


class PostCreate(BaseModel):
    """建立貼文請求模型。"""

    content: str = Field(..., min_length=1, max_length=2000)


class SessionRequest(BaseModel):
    """QR 會話操作請求模型。"""

    session_id: str


class LoginResponse(BaseModel):
    """登入成功回應模型。"""

    username: str
    token: str


@dataclass
class QrSession:
    """單一 QR Code 登入會話狀態。"""

    created_at: datetime
    status: str = "pending"
    user: Optional[str] = None


# ---------------------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------------------
def utc_now() -> datetime:
    """取得含時區資訊的 UTC 當前時間。"""
    return datetime.now(timezone.utc)


def generate_qr_code_data_uri(payload: str) -> str:
    """將字串內容編碼為 Base64 PNG Data URI，供前端直接顯示 QR Code。"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# 核心服務（可脫離 FastAPI 獨立進行單元測試）
# ---------------------------------------------------------------------------
class BoardService:
    """封裝會話生命週期、JWT 驗證與留言板資料操作。"""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._sessions: Dict[str, QrSession] = {}
        self._posts: List[Post] = []

    def create_access_token(
        self,
        username: str,
        expires_minutes: Optional[int] = None,
    ) -> str:
        """簽發包含到期時間的 JWT 存取權杖。"""
        minutes = expires_minutes or self._config.access_token_expire_minutes
        payload = {
            "sub": username,
            "exp": utc_now() + timedelta(minutes=minutes),
        }
        return jwt.encode(
            payload,
            self._config.jwt_secret_key,
            algorithm=self._config.jwt_algorithm,
        )

    def verify_access_token(self, token: str) -> str:
        """驗證 JWT 並回傳使用者名稱，無效或過期時拋出 ValueError。"""
        try:
            payload = jwt.decode(
                token,
                self._config.jwt_secret_key,
                algorithms=[self._config.jwt_algorithm],
            )
        except jwt.PyJWTError as exc:
            raise ValueError("無效或已過期的存取權杖") from exc

        username = payload.get("sub")
        if not username:
            raise ValueError("權杖缺少使用者識別資訊")
        return str(username)

    def create_qr_session(self) -> str:
        """建立新的待掃描 QR 登入會話並回傳 session_id。"""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = QrSession(created_at=utc_now())
        return session_id

    def get_session(self, session_id: str) -> Optional[QrSession]:
        """查詢指定會話，不存在時回傳 None。"""
        return self._sessions.get(session_id)

    def authenticate_session(
        self,
        session_id: str,
        username: str = DEFAULT_DEMO_USERNAME,
    ) -> LoginResponse:
        """驗證 QR 會話並標記為已登入，回傳登入資訊與 JWT。"""
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError("會話不存在或已過期")

        session.status = "authenticated"
        session.user = username
        session.created_at = utc_now()
        token = self.create_access_token(
            username,
            expires_minutes=self._config.qr_token_expire_minutes,
        )
        return LoginResponse(username=username, token=token)

    def remove_session(self, session_id: str) -> None:
        """登出並移除指定會話。"""
        self._sessions.pop(session_id, None)

    def purge_expired_sessions(self) -> list[str]:
        """清除所有超過存活時間的會話並回傳已移除的 session_id 清單。"""
        ttl = timedelta(minutes=self._config.session_ttl_minutes)
        now = utc_now()
        expired_ids = [
            sid for sid, sess in list(self._sessions.items()) if now - sess.created_at > ttl
        ]
        for sid in expired_ids:
            self._sessions.pop(sid, None)
        return expired_ids

    def list_posts(self) -> List[Post]:
        """取得所有貼文清單（最新在前）。"""
        return self._posts

    def create_post(self, username: str, content: str) -> Post:
        """建立新貼文並置頂於貼文清單。"""
        post = Post(
            id=len(self._posts) + 1,
            username=username,
            content=content,
            timestamp=utc_now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._posts.insert(0, post)
        return post

    def add_comment(self, post_id: int, username: str, content: str) -> Comment:
        """於指定貼文下新增留言，找不到貼文時拋出 KeyError。"""
        target_post = next((post for post in self._posts if post.id == post_id), None)
        if target_post is None:
            raise KeyError("指定的貼文不存在")

        comment = Comment(
            id=len(target_post.comments) + 1,
            username=username,
            content=content,
            timestamp=utc_now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        target_post.comments.append(comment)
        return comment
