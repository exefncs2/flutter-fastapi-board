"""FastAPI backend for Flutter FastAPI Board.

Provides QR-code session authentication over WebSocket (with HTTP polling
fallback), JWT bearer authentication, and post/comment REST endpoints.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import jwt
import qrcode
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("flutter_fastapi_board")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "15"))

# ---------------------------------------------------------------------------
# In-memory storage (replace with PostgreSQL / Redis in production)
# ---------------------------------------------------------------------------
USERS: Dict[str, Dict[str, str]] = {
    "user1": {"username": "user1", "full_name": "Demo User", "email": "user1@example.com"}
}
active_sessions: Dict[str, Dict[str, object]] = {}
connected_clients: Dict[str, WebSocket] = {}
POSTS: List["Post"] = []


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class Comment(BaseModel):
    id: int
    username: str
    content: str
    timestamp: str


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class Post(BaseModel):
    id: int
    username: str
    content: str
    timestamp: str
    comments: List[Comment] = Field(default_factory=list)


class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class SessionRequest(BaseModel):
    session_id: str


class LoginResponse(BaseModel):
    username: str
    token: str


# ---------------------------------------------------------------------------
# Auth & QR Helpers
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_qr_code(data: str) -> str:
    """Encode payload string into a base64 PNG data URI."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = utc_now() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Validate Bearer JWT and return the authenticated username."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無效的令牌")
        return username
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無效或已過期的令牌") from exc


# ---------------------------------------------------------------------------
# Background Session Cleanup & App Lifespan
# ---------------------------------------------------------------------------
async def cleanup_expired_sessions() -> None:
    """Periodically evict expired QR login sessions and close stale sockets."""
    ttl = timedelta(minutes=SESSION_TTL_MINUTES)
    while True:
        now = utc_now()
        expired_ids = [
            sid
            for sid, sess in list(active_sessions.items())
            if isinstance(sess.get("created_at"), datetime) and now - sess["created_at"] > ttl
        ]
        for sid in expired_ids:
            active_sessions.pop(sid, None)
            client = connected_clients.pop(sid, None)
            if client is not None:
                with suppress(Exception):
                    await client.close()
        if expired_ids:
            logger.info("Cleaned up %d expired QR session(s)", len(expired_ids))
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(cleanup_expired_sessions())
    logger.info("QR session cleanup background task started")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        logger.info("QR session cleanup background task stopped")


# ---------------------------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Flutter FastAPI Board",
    description="QR Code authentication & real-time bulletin board API",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Web & WebSocket Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "created_at": utc_now(),
        "status": "pending",
        "user": None,
    }
    qr_payload = json.dumps({"session_id": session_id})
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "qr_code": generate_qr_code(qr_payload),
            "session_id": session_id,
        },
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if session_id not in active_sessions:
        await websocket.close(code=1008, reason="Session 不存在")
        return

    connected_clients[session_id] = websocket
    try:
        while True:
            await websocket.receive_text()
            session = active_sessions.get(session_id)
            if not session:
                await websocket.send_json({"status": "expired"})
                break
            if session["status"] == "authenticated":
                token = create_access_token({"sub": session["user"]})
                await websocket.send_json(
                    {"status": "authenticated", "user": session["user"], "token": token}
                )
            else:
                await websocket.send_json({"status": session["status"]})
    except WebSocketDisconnect:
        connected_clients.pop(session_id, None)


# ---------------------------------------------------------------------------
# Authentication API
# ---------------------------------------------------------------------------
@app.post("/api/qr-login", response_model=LoginResponse)
async def qr_login(payload: SessionRequest):
    session = active_sessions.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session 不存在或已過期")

    username = "user1"
    session.update({"status": "authenticated", "user": username, "created_at": utc_now()})
    token = create_access_token({"sub": username}, expires_delta=timedelta(hours=1))

    ws = connected_clients.get(payload.session_id)
    if ws is not None:
        try:
            await ws.send_json({"status": "authenticated", "user": username, "token": token})
        except Exception as exc:
            logger.warning("WebSocket notification failed for %s: %s", payload.session_id, exc)

    return LoginResponse(username=username, token=token)


@app.post("/api/logout")
async def logout(payload: SessionRequest):
    active_sessions.pop(payload.session_id, None)
    ws = connected_clients.pop(payload.session_id, None)
    if ws is not None:
        with suppress(Exception):
            await ws.send_json({"status": "logout", "message": "已登出"})
    return {"status": "success", "message": "已登出"}


@app.get("/api/check-session/{session_id}")
async def check_session(session_id: str):
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session 不存在或已過期")
    return {"status": session["status"], "user": session.get("user")}


# ---------------------------------------------------------------------------
# Posts & Comments API
# ---------------------------------------------------------------------------
@app.get("/api/posts", response_model=List[Post])
async def get_posts(_username: str = Depends(get_current_user)):
    return POSTS


@app.post("/api/posts", response_model=Post, status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate, username: str = Depends(get_current_user)):
    new_post = Post(
        id=len(POSTS) + 1,
        username=username,
        content=post.content,
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    POSTS.insert(0, new_post)
    return new_post


@app.post("/api/posts/{post_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: int,
    comment: CommentCreate,
    username: str = Depends(get_current_user),
):
    post = next((p for p in POSTS if p.id == post_id), None)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="貼文不存在")

    new_comment = Comment(
        id=len(post.comments) + 1,
        username=username,
        content=comment.content,
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    post.comments.append(new_comment)
    return new_comment


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
