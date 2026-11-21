# Flutter FastAPI Board

整合 **QR Code 跨裝置即時登入** 與 **JWT 留言評論功能** 的前後端分離練習專案（後端 FastAPI、行動端 Flutter）。

## 1. 緣起與想驗證的事情

平常看 LINE 或網頁版服務「電腦顯示 QR Code、手機掃描後網頁自動跳轉登入」覺得很方便，因此自己動手做一組最小可行實作，把整個驗證流程、即時狀態通知與登入後的 JWT API 權限串起來。

---

## 2. 設計思路與關鍵取捨

### (1) QR Code 跨裝置登入流程怎麼設計？
1. 網頁端打開 `/` 時，後端建立一個帶 UUID 的 `pending` 會話，把 `{"session_id": "..."}` 編成 Base64 QR Code 顯示在畫面上。
2. 網頁端同時建立 WebSocket 連線（`/ws/{session_id}`）等待登入狀態變更。
3. 手機 Flutter App 掃描 QR Code 取得 `session_id`，呼叫 `POST /api/qr-login` 確認登入。
4. 後端將該會話標記為 `authenticated`、簽發 JWT，並直接透過對應的 WebSocket 推播給網頁端完成登入。

### (2) 為什麼除了 WebSocket 還留一條 HTTP 輪詢端點？
- WebSocket 即時性最好，但實務上經過反向代理或網路切換時容易斷線。保留 `GET /api/check-session/{session_id}` 當作降級備援，就算 WebSocket 中斷，前端也能輪詢拿到登入狀態。

### (3) 為什麼要加背景清理協程與三檔分離？
- 每次打開登入頁都會產生一筆會話，若使用者關掉視窗沒掃描，會話會一直留在記憶體裡。因此透過 FastAPI `lifespan` 在啟動時開啟定時清理協程，自動清掉超過 TTL 的過期會話並關閉對應連線。
- 後端拆成 `config.py`（設定與邊界檢查）、`service.py`（`BoardService` 封裝會話、JWT 與貼文留言邏輯）、`main.py`（純 HTTP / WebSocket 路由），讓商業邏輯不會和路由綁死。

---

## 3. 目前已知限制

- **記憶體暫存**：目前會話、貼文與留言皆存在記憶體內，後端重啟資料就會歸零；若要上線，會話應改存 Redis（直接利用 TTL 自動過期），貼文資料改存 PostgreSQL。
- **示範帳號流程**：目前為簡化版單一示範帳號（`user1`）驗證，尚未加上註冊、密碼雜湊與 Refresh Token 機制。

---

## 4. 專案結構

```text
flutter-fastapi-board/
├── backend/
│   ├── config.py        # 環境變數載入、常數與 AppConfig 檢核
│   ├── service.py       # QR 會話管理、JWT 簽發驗證與留言板核心邏輯
│   ├── main.py          # FastAPI HTTP / WebSocket 路由與生命週期管理
│   ├── templates/       # 網頁端 QR 登入頁面
│   ├── static/          # 網頁樣式
│   ├── tests/           # 設定載入單元測試
│   ├── .env.example
│   └── requirements.txt
└── frontend/            # Flutter 行動端專案（掃碼登入、留言列表、發表與回覆）
```

## 5. 執行方式

### 後端（FastAPI）
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python main.py
```
啟動後網頁端登入畫面在 `http://localhost:8000`，Swagger 文件在 `http://localhost:8000/docs`。

### 前端（Flutter）
```bash
cd frontend
flutter pub get
flutter run
```
執行前請依本機網路環境於前端設定對應的後端伺服器位址。
