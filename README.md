# Flutter FastAPI Board

整合 **QR Code 掃描登入** 與 **即時留言評論功能** 的跨平台行動應用範例，使用 **FastAPI（Python）** 作為後端 API 服務、**Flutter（Dart）** 作為 iOS／Android 前端介面。

## 功能特色

- **QR Code 掃描認證登入**：透過行動裝置掃描網頁端或範例 QR Code 完成快速登入。
- **即時留言與評論系統**：前後端透過 RESTful API 進行資料同步與評論互動。
- **跨平台支援**：單一 Flutter 程式碼庫同時支援 Android 與 iOS。

## 技術架構

| 層級 | 技術選型 |
| :--- | :--- |
| **前端（Mobile）** | Flutter (Dart) |
| **後端（API）** | FastAPI (Python) |
| **通訊協定** | RESTful API |
| **身分驗證** | QR Code 認證流程 |

## 安裝與啟動指南

### 後端服務（FastAPI）

```bash
cd backend
pip install -r requirements.txt
python main.py
```

啟動後預設運行於 `http://localhost:8000`（API 文件可於 `/docs` 檢視）。

### 前端應用（Flutter）

1. 確認本機已完成 Flutter 環境安裝：

```bash
flutter doctor
```

2. 安裝相依套件並啟動應用：

```bash
cd frontend
flutter pub get
flutter run
```

## 使用流程

1. 啟動後端 FastAPI 服務。
2. 在模擬器或實體手機（Android 需開啟 USB 偵錯）啟動 Flutter 應用程式。
3. 使用 App 內建 QR Code 掃描器登入，即可開始使用留言評論功能。
