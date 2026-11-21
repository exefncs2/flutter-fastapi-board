# Flutter FastAPI Board

![Flutter](https://img.shields.io/badge/Flutter-Dart-02569B?logo=flutter&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white)
![WebSocket](https://img.shields.io/badge/Realtime-WebSocket%20%2B%20JWT-4A154B)

整合 **QR Code 掃描即時登入**（WebSocket＋輪詢備援）與 **JWT 留言評論功能** 的跨平臺行動應用範例。後端採**三檔分離架構**（設定 / 核心服務 / 路由進入點），前端使用 Flutter 支援 Android 與 iOS。

## 專案結構

```text
flutter-fastapi-board/
├── backend/
│   ├── config.py        # 參數設定檔：環境變數載入、常數與不可變 AppConfig
│   ├── service.py       # 核心邏輯檔：QR 會話生命週期、JWT 驗證、貼文與留言領域服務
│   ├── main.py          # 呼叫進入點：FastAPI HTTP / WebSocket 路由與生命週期管理
│   ├── templates/       # 網頁端 QR 登入畫面
│   ├── static/          # 樣式表
│   ├── .env.example     # 環境變數範本
│   └── requirements.txt # 精簡修補版後端依賴
└── frontend/            # Flutter 跨平臺行動端專案
```

## 快速開始

### 後端服務（FastAPI）

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python main.py
```

服務啟動後預設運行於 `http://localhost:8000`（API 文件可於 `/docs` 檢視）。

### 前端應用（Flutter）

```bash
cd frontend
flutter doctor
flutter pub get
flutter run
```
