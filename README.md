# Flutter FastAPI Board（Fack_Book 跨裝置 QR 登入與留言板實作筆記）

> 使用 **FastAPI（Python）** 與 **Flutter（Dart）** 串接的跨平台應用技術練習，紀錄「網頁端顯示 QR Code → 手機掃描驗證 → 網頁即時登入＋JWT 留言板」的完整實作過程。

## 1. 學習目標與架構想法

這個專案主要想練習三件事：
1. **跨裝置 QR Code 即時登入**：模擬常見網頁版通訊軟體的掃碼登入體驗，讓電腦網頁與手機 App 透過同一個 `session_id` 完成驗證。
2. **前後端分離與 JWT 權限保護**：行動端登入取得 Token 後，透過 Bearer Token 呼叫發文與留言 API，並支援重新開啟 App 時的自動登入驗證（`/api/users/me`）。
3. **跨平台行動端操作**：練習 Flutter 的 Provider 狀態管理、安全儲存（Secure Storage）與相機 QR 掃描流程。

---

## 2. 設計思路與實作筆記

### (1) QR Code 登入與即時通知流程
1. 瀏覽器開啟登入頁 `/` → 後端建立一組 UUID 會話（狀態為 `pending`），將 `{"session_id": "..."}` 轉成 Base64 PNG QR Code 渲染至頁面。
2. 瀏覽器同步建立 WebSocket 連線（`/ws/{session_id}`）等待驗證結果。
3. Flutter App 掃碼取得 `session_id` 後呼叫 `POST /api/qr-login` → 後端更新會話狀態為 `authenticated`、簽發 JWT，並即時透過 WebSocket 推播登入成功與 Token 給網頁端。

### (2) 為什麼保留 WebSocket + HTTP 輪詢雙重機制？
- 正常情況下 WebSocket 可以毫秒級通知網頁端跳轉；但在部分網路環境或代理下 WebSocket 可能中斷，因此保留 `GET /api/check-session/{session_id}` 作為降級輪詢備援。

### (3) 資源清理與後端三檔整理
- 每次載入登入頁都會建立會話，為避免沒掃描的過期會話堆積在記憶體裡，透過 FastAPI `lifespan` 在啟動時啟動背景清理協程，定期清除超過 TTL 的會話並關閉對應 WebSocket。
- 後端採三檔分離：`config.py`（設定與邊界檢查）、`service.py`（`BoardService` 封裝會話、JWT 與貼文留言狀態）、`main.py`（HTTP / WebSocket 路由進入點），讓核心邏輯可獨立維護。

### (4) 目前已知限制
- 會話與貼文目前皆暫存在記憶體（重啟服務會清空），且登入僅為示範帳號流程（`user1`）；若要進一步往正式環境演進，會話建議改存 Redis、貼文改存關聯式資料庫，並補上帳號密碼雜湊驗證。

---

## 3. 專案結構

```text
flutter-fastapi-board/
├── backend/
│   ├── config.py        # 環境變數與安全常數設定
│   ├── service.py       # QR 會話生命週期、JWT 驗證與留言板邏輯
│   ├── main.py          # FastAPI HTTP / WebSocket 路由與生命週期管理
│   ├── templates/       # 網頁端 QR 登入畫面
│   ├── static/          # 樣式表
│   ├── tests/           # 設定單元測試
│   ├── .env.example
│   └── requirements.txt
└── frontend/            # Flutter 行動端專案（支援 Android / iOS）
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
服務啟動後預設於 `http://localhost:8000` 顯示 QR 登入頁面（API 文件位於 `http://localhost:8000/docs`）。

執行後端設定單元測試：
```bash
cd backend
python -m unittest discover -s tests -v
```

### 前端啟動（Flutter）
1. 確認本機已安裝 Flutter 環境（安裝教學可參考：[iT 邦幫忙 Flutter 環境建置教學](https://ithelp.ithome.com.tw/m/articles/10216013)），執行 `flutter doctor` 檢查。
2. 連接實機（Android 請開啟 USB 偵錯模式）或啟動模擬器，並執行：
```bash
cd frontend
flutter pub get
flutter run
```
3. 啟動後開啟 App 內的 QR 掃描功能，掃描網頁端 `http://localhost:8000` 顯示的 QR Code 即可登入並測試發文與留言功能。
