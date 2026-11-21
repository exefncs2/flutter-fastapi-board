# Flutter FastAPI Board（Fack_Book 學習與快速實作紀錄）

> 本專案是一個用 **FastAPI 內建功能** 與 **Flutter** 快速串接起來的跨平台留言板原型，目的是練習把「網頁顯示 QR Code → 手機掃描登入 → 取得 JWT 發表貼文與留言」整條流程跑通。

## 1. 這一版實際上怎麼寫的（對照程式碼）

本版刻意求快、不接外部資料庫，全部直接用現成套件與記憶體內建結構串起來：

1. **網頁顯示 QR Code（`backend/main.py` + `templates/login.html`）**
   - 瀏覽器開啟 `/` 時，後端用 Python 內建 `uuid.uuid4()` 產生一組暫時配對 ID，放進記憶體 `dict`（預設狀態 `pending`），再用 `qrcode` 套件轉成 Base64 圖片塞進 Jinja2 頁面。
   - 頁面載入後用瀏覽器原生 `WebSocket` 連向 `/ws/{id}` 等待狀態更新；若 WebSocket 沒連上或中斷，頁面上有寫一段簡單的 `setInterval` 改打 `/api/check-session/{id}` 檢查狀態。
2. **手機掃碼與簡易認證（`frontend/lib/screens/qr_scanner_screen.dart` + `backend/service.py`）**
   - Flutter 端直接用 `mobile_scanner` 掃描 QR Code 裡的 JSON，送 `POST /api/qr-login` 給後端。
   - 後端把該筆記憶體狀態改為 `authenticated`、直接套用固定示範帳號 `user1`、用 `PyJWT` 簽出一組 Token 回傳給手機，並透過原本開著的 WebSocket 通知網頁端切換成「登入成功」畫面。
3. **留言板與過期清理**
   - 貼文與留言全部暫存在記憶體 Python `list` 中，透過 FastAPI 內建的 `OAuth2PasswordBearer` 驗證 Bearer Token 後操作 `/api/posts`、`/api/posts/{post_id}/comments` 與 `/api/users/me`。
   - 透過 FastAPI `lifespan` 開一個 `asyncio` 迴圈，每 60 秒清掉記憶體 `dict` 裡超過 TTL（預設 15 分鐘）的過期項目。
4. **程式碼整理**
   - 原本後端全寫在單一 `main.py`，後續拆成 `config.py`（設定常數）、`service.py`（記憶體資料與 JWT 處理）、`main.py`（路由進入點），方便閱讀與單獨測設定載入。

---

## 2. 目前範圍與限制

- 屬於快速驗證原型：所有資料（配對狀態、貼文、留言）都存在記憶體內，重啟後端即清空。
- 帳號為單一固定示範使用者 `user1`，沒有註冊、密碼驗證與資料庫持久化。

---

## 3. 專案結構

```text
flutter-fastapi-board/
├── backend/
│   ├── config.py        # 環境變數與預設常數設定
│   ├── service.py       # 記憶體配對狀態、JWT 簽發驗證與貼文留言操作
│   ├── main.py          # FastAPI HTTP / WebSocket 路由與背景清理任務
│   ├── templates/       # 網頁端 QR 登入畫面（base.html / login.html）
│   ├── static/          # 樣式表（styles.css）
│   ├── tests/           # 設定載入單元測試
│   ├── .env.example
│   └── requirements.txt
└── frontend/            # Flutter 專案（掃碼、登入狀態儲存、貼文與留言畫面）
```

---

## 4. 正式使用方式

### 後端啟動（FastAPI）
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python main.py
```
啟動後預設於 `http://localhost:8000` 顯示 QR Code 頁面，API 文件位於 `http://localhost:8000/docs`。

執行後端設定單元測試：
```bash
cd backend
python -m unittest discover -s tests -v
```

### 前端啟動（Flutter）
1. 確認本機已安裝 Flutter（參考：[iT 邦幫忙 Flutter 環境建置教學](https://ithelp.ithome.com.tw/m/articles/10216013)），執行 `flutter doctor` 確認環境。
2. 連接 Android 實機（開啟 USB 偵錯模式）或模擬器後執行：
```bash
cd frontend
flutter pub get
flutter run
```
3. 進入 App 點選掃描按鈕，對準 `http://localhost:8000` 畫面上的 QR Code 即可登入測試發文與留言。
