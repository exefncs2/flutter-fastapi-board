"""FastAPI 呼叫進入點：負責 HTTP / WebSocket 路由對應與背景任務生命週期。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import json
import logging
from typing import Dict, List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import (
    AppConfig,
    SESSION_CLEANUP_INTERVAL_SECONDS,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from service import (
    BoardService,
    Comment,
    CommentCreate,
    LoginResponse,
    Post,
    PostCreate,
    SessionRequest,
    generate_qr_code_data_uri,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("flutter_fastapi_board")

config = AppConfig.from_env()
board_service = BoardService(config)
connected_clients: Dict[str, WebSocket] = {}
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """驗證 Bearer Token 並回傳當前使用者名稱。"""
    try:
        return board_service.verify_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


async def _cleanup_loop() -> None:
    """背景定時清除過期會話並關閉對應的 WebSocket 連線。"""
    while True:
        expired_ids = board_service.purge_expired_sessions()
        for sid in expired_ids:
            client = connected_clients.pop(sid, None)
            if client is not None:
                with suppress(Exception):
                    await client.close()
        if expired_ids:
            logger.info("已清理 %d 筆過期 QR 登入會話", len(expired_ids))
        await asyncio.sleep(SESSION_CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """管理背景清理協程隨應用程式啟動與優雅關閉。"""
    cleanup_task = asyncio.create_task(_cleanup_loop())
    logger.info("QR 會話背景清理任務已啟動")
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        logger.info("QR 會話背景清理任務已停止")


app = FastAPI(
    title="Flutter FastAPI Board",
    description="QR Code 即時認證登入與留言評論系統 API",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """渲染 QR Code 登入頁面並建立待掃描會話。"""
    session_id = board_service.create_qr_session()
    qr_payload = json.dumps({"session_id": session_id})
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "qr_code": generate_qr_code_data_uri(qr_payload),
            "session_id": session_id,
        },
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """維持前端 WebSocket 連線並即時推送 QR 登入狀態變更。"""
    await websocket.accept()
    if board_service.get_session(session_id) is None:
        await websocket.close(code=1008, reason="會話不存在")
        return

    connected_clients[session_id] = websocket
    try:
        while True:
            await websocket.receive_text()
            session = board_service.get_session(session_id)
            if session is None:
                await websocket.send_json({"status": "expired"})
                break
            if session.status == "authenticated" and session.user:
                token = board_service.create_access_token(session.user)
                await websocket.send_json(
                    {"status": "authenticated", "user": session.user, "token": token}
                )
            else:
                await websocket.send_json({"status": session.status})
    except WebSocketDisconnect:
        connected_clients.pop(session_id, None)


@app.post("/api/qr-login", response_model=LoginResponse)
async def qr_login(payload: SessionRequest) -> LoginResponse:
    """處理行動端掃碼確認，更新會話狀態並即時通知網頁端。"""
    try:
        login_result = board_service.authenticate_session(payload.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    client = connected_clients.get(payload.session_id)
    if client is not None:
        try:
            await client.send_json(
                {
                    "status": "authenticated",
                    "user": login_result.username,
                    "token": login_result.token,
                }
            )
        except Exception as exc:
            logger.warning("推送 WebSocket 登入通知失敗（session=%s）：%s", payload.session_id, exc)

    return login_result


@app.post("/api/logout")
async def logout(payload: SessionRequest) -> dict[str, str]:
    """登出並移除對應會話。"""
    board_service.remove_session(payload.session_id)
    client = connected_clients.pop(payload.session_id, None)
    if client is not None:
        with suppress(Exception):
            await client.send_json({"status": "logout", "message": "已登出"})
    return {"status": "success", "message": "已登出"}


@app.get("/api/check-session/{session_id}")
async def check_session(session_id: str) -> dict[str, str | None]:
    """提供 WebSocket 異常時的 HTTP 輪詢狀態查詢介面。"""
    session = board_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="會話不存在或已過期")
    return {"status": session.status, "user": session.user}


@app.get("/api/posts", response_model=List[Post])
async def get_posts(_username: str = Depends(get_current_user)) -> List[Post]:
    """取得所有貼文清單。"""
    return board_service.list_posts()


@app.post("/api/posts", response_model=Post, status_code=status.HTTP_201_CREATED)
async def create_post(
    post: PostCreate,
    username: str = Depends(get_current_user),
) -> Post:
    """建立新貼文。"""
    return board_service.create_post(username=username, content=post.content)


@app.post("/api/posts/{post_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: int,
    comment: CommentCreate,
    username: str = Depends(get_current_user),
) -> Comment:
    """於指定貼文新增留言。"""
    try:
        return board_service.add_comment(
            post_id=post_id,
            username=username,
            content=comment.content,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
