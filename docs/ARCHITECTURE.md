# 系統架構設計：AI 聊天機器人 (AI Chatbot)

## 1. 架構總覽

```mermaid
graph TD
    Client[前端網頁 (HTML/Vanilla JS)] -->|HTTP GET/POST / RESTful API| FastAPI[後端 API 伺服器 (FastAPI)]
    Client -->|WebSocket / Server-Sent Events| FastAPI
    FastAPI -->|SQLAlchemy 讀取/寫入| SQLite[(SQLite 資料庫)]
    FastAPI -->|Prompt & 歷史對話| LLM[Google Gemini API]
    FastAPI -->|API 請求| Tools[外部工具 API]
```

## 2. 系統組件架構

### 2.1 前端介面 (Client-Side)
- **職責**：處理使用者操作（打字、點擊切換、上傳檔案）、呈現對話氣泡與歷史列表、處理不同 session 的視覺切換。
- **核心模組**：
  - `Chat UI 控制器`：負責處理對話視窗的最新訊息繪製與滾動條定位。
  - `Session 管理器`：向後端請求過去的 Session 清單，提供切換當前視窗狀態的功能。
  - `檔案處理器 (File Handler)`：圖片與文件的上傳前預覽，並轉換格式（如 multipart/form-data 或是 Base64）給後端。
  - `狀態控制台 (Control Panel)`：提供使用者「中止對話 (Stop)」、「重新生成 (Regenerate)」的按鈕邏輯。

### 2.2 後端服務 (Server-Side)
- **職責**：處理並路由前端請求、管理資料庫存取、維護對話狀態、調用外部大語言模型。
- **核心模組**：
  - `Router 層 (API 路由)`：定義 API 端點（例如 `/chat`, `/sessions`, `/upload`），規範輸入輸出格式。
  - `Session & Memory 服務`：管理不同聊天室的狀態，負責將對話歷史上下文從資料庫中撈取，並接上系統提示語（System Prompt）。
  - `LLM 代理服務 (Agent Service)`：與 Gemini API 溝通，組裝完整 Prompt（包含圖片），並接收及轉發 Streaming 長回應給前端。
  - `工具控制器 (Tool Controller)`：被代理喚醒後，處理外部 API 請求（例如查詢天氣、搜尋網路），並將結果包裝丟回給 LLM 分析。

### 2.3 資料持久層 (Database)
- **職責**：確保應用重啟後依然保存對話結構、多重 session 以及使用者偏好。
- **核心模組**：
  - `Sessions 表`：儲存多個聊天室的基本資訊。
  - `Messages 表`：綁定外鍵至 Sessions，紀錄發送者角色 (role)、內容 (content) 及精確建立時間。
  - `Preferences 表`：記錄使用者的個人化指令或系統設定。

## 3. API 溝通模式設計

### 3.1 RESTful API
- **用途**：取得歷史紀錄清單、上傳圖片檔案、建立新對話、刪除對話、更新個人化設定。
- **優勢**：標準化、直觀、易於用原生的 `fetch()` 處理。

### 3.2 針對對話生成的串流 (Server-Sent Events / Streaming endpoints)
- **用途**：應對 AI 回答的 Streaming (串流) 輸出文字。
- **優勢**：確保打字機效果，AI 每生成一個片段就可以即時回傳前端，使用者不需要等待完整文章產出。

## 4. 技術選型

### 4.1 前端 (Frontend)
- **標記與樣式**：HTML5, CSS3。
- **邏輯與互動**：Vanilla JavaScript（原生 JS）配合 Fetch API。
- **理由**：不依賴複雜框架，維持輕量體積並專注於資料的即時渲染。

### 4.2 後端 (Backend)
- **框架**：Python + FastAPI。
- **應用伺服器**：Uvicorn (支援 ASGI，完美發揮 FastAPI 的非同步優勢)。
- **AI 整合**：`google-generativeai` 官方 SDK 提供 Gemini API 連線機制。
- **理由**：FastAPI 提供原生的非同步 (async) 支援以及自動文件 (Swagger UI)，大幅提升串流回應效能及開發體驗。

### 4.3 資料庫 (Database)
- **資料庫引擎**：SQLite。
- **ORM 套件**：SQLAlchemy 或 SQLModel。
- **理由**：無須額外架設資料庫伺服器，將資料庫儲存於單個 `.db` 檔案，適合目前開發需求並能維持關聯式結構的嚴謹性。

## 5. 效能與安全性優化考量

### 5.1 體驗與效能優化
- **串流 (Streaming)**：是聊機機器人的核心體驗，大幅縮短使用者的體感等候時間 (TTFB)。
- **前端本地緩存**：可將未送出的打字暫存，或快取最新一個 session 的對話。

### 5.2 系統安全性
- **CORS 設定**：透過 FastAPI 中介軟體設定允許來源，保護後端不被任意跨網來源存取。
- **機密環境變數**：嚴格落實將 `GEMINI_API_KEY` 等外部憑證寫在 `.env`，並確保其不進入版控 (`.gitignore`)。
- **檔案防護**：上傳圖片時需在後端驗證 MIME type 與檔案大小上限，防禦惡意請求或記憶體溢出。
