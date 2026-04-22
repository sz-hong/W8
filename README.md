# AI 聊天機器人 (AI Chatbot) - 作業專案

本專案使用 Antigravity Skill 引導 AI，完成了一個具備前後端的 AI 聊天機器人。

## 功能特點
-   **對話狀態管理**：支援多聊天室（session），維持上下文。
-   **訊息系統**：訊息結構包含 role、content、timestamp。
-   **對話歷史管理**：可顯示並切換過去的對話紀錄。
-   **上傳圖片或文件**：支援使用者上傳圖片作為對話內容。
-   **回答控制**：提供重新生成（regenerate）或在生成時中止回應的控制功能。
-   **記憶機制**：儲存使用者偏好，實現跨對話持續性記憶。
-   **工具整合**：攔截文字內容並以外部工具 API 模擬提供實時觀測數據。

## 開發技術棧
- **Frontend**: 原生 HTML, CSS, Vanilla JavaScript (含 SSE Streaming, Fetch API)。
- **Backend**: Python 3.14, FastAPI, Uvicorn。
- **Database**: SQLite (透過 SQLAlchemy ORM)。
- **LLM**: Google Generative AI (Gemini 2.5 Flash)。

## 啟動方式

```bash
# 1. 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. 安裝套件
pip install -r requirements.txt
pip install Pillow  # 處理圖檔需求

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env，填入 GEMINI_API_KEY

# 4. 啟動伺服器
uvicorn app:app --reload
# 開啟瀏覽器：http://localhost:8000
```

---

## 心得報告

**姓名**：洪士智 (Sz-hong) 
**學號**：(請填寫)
**信箱**：thomas931208@gmail.com

### 問題與反思

**Q1. 你設計的哪一個 Skill 效果最好？為什麼？哪一個效果最差？你認為原因是什麼？**

> （在此填寫）

---

**Q2. 在用 AI 產生程式碼的過程中，你遇到什麼問題是 AI 沒辦法自己解決、需要你介入處理的？**

> 最大的問題在於版本與環境相依性。例如在實作過程中，原先鎖定舊版的 `pydantic==2.7.4`，但因為我的本機使用極新的 Python 3.14 版本，導致底層 Rust 套件編譯失敗，這需要透過手動介入修改 `requirements.txt` 解除版本限制才得以解決。此外，AI 難以確保每一次都能完整掌握所需套件，例如忘了將 `Pillow` 寫入依賴中，這也需要依賴明確報錯訊息後再請 AI 修正。（您可以依照自身感受進行補寫）
