import os
import json
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime
from PIL import Image
from io import BytesIO

from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session as DBSession

from dotenv import load_dotenv
import google.generativeai as genai

# ==========================================
# 1. 初始化與環境設定
# ==========================================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="AI Chatbot API")

# 確保 templates 和 uploads 目錄存在
os.makedirs("templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

templates = Jinja2Templates(directory="templates")

# ==========================================
# 2. 資料庫與 SQLAlchemy 模型
# ==========================================
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ChatSession(Base):
    __tablename__ = 'sessions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('sessions.id'), nullable=False, index=True)
    role = Column(String(20), nullable=False) # 'user' or 'model'
    content = Column(Text, nullable=False)
    has_attachment = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="messages")

class UserPreference(Base):
    __tablename__ = 'user_preferences'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), default="default", index=True)
    settings_key = Column(String(50), nullable=False)
    settings_value = Column(String(200), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 3. 工具函式 (Tool Calling Mock)
# ==========================================
def fetch_weather(city: str) -> str:
    """模擬工具：查詢天氣 (這裡真實呼叫 wttr.in API)"""
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=3"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        return f"無法獲取 {city} 的天氣資訊。"

# ==========================================
# 4. API 路由與端點
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/sessions")
def create_session(db: DBSession = Depends(get_db)):
    db_session = ChatSession(title=f"New Chat {datetime.now().strftime('%H:%M')}")
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return {"id": db_session.id, "title": db_session.title}

@app.get("/sessions")
def get_sessions(db: DBSession = Depends(get_db)):
    sessions = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
    return [{"id": s.id, "title": s.title, "updated_at": s.updated_at} for s in sessions]

@app.get("/sessions/{session_id}/messages")
def get_messages(session_id: int, db: DBSession = Depends(get_db)):
    messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id.asc()).all()
    return [{"id": m.id, "role": m.role, "content": m.content, "has_attachment": m.has_attachment} for m in messages]

@app.post("/preferences")
def save_preference(key: str = Form(...), value: str = Form(...), db: DBSession = Depends(get_db)):
    pref = db.query(UserPreference).filter(UserPreference.user_id == "default", UserPreference.settings_key == key).first()
    if pref:
        pref.settings_value = value
    else:
        pref = UserPreference(user_id="default", settings_key=key, settings_value=value)
        db.add(pref)
    db.commit()
    return {"status": "success", "key": key, "value": value}

@app.get("/preferences")
def get_preferences(db: DBSession = Depends(get_db)):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == "default").all()
    return {p.settings_key: p.settings_value for p in prefs}

# 核心聊天邏輯 (包含檔案解析、歷史合併、系統指令、Streaming 回傳)
@app.post("/chat/{session_id}")
async def chat(session_id: int, message: str = Form(""), file: UploadFile = File(None), db: DBSession = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    has_attachment = file is not None and file.filename != ""
    if not message and not has_attachment:
        raise HTTPException(status_code=400, detail="Empty message")

    user_msg = Message(session_id=session_id, role="user", content=message or "[傳送了檔案]", has_attachment=has_attachment)
    db.add(user_msg)
    
    # 簡單工具攔截：如果內文提到天氣，我們偷偷幫他掛上工具結果
    tool_context = ""
    if "天氣" in message:
        # 取巧找出關鍵字，比如 "台北天氣"、"台中天氣"
        cities = ["台北", "台中", "高雄", "花蓮", "東京", "倫敦", "紐約", "台南"]
        for c in cities:
            if c in message:
                w = fetch_weather(c)
                tool_context += f"[系統觀測工具：已經幫你查好 {c} 的天氣是 '{w}'，請參考此資訊回覆使用者。]"
                break
                
    db.commit()

    # 組織 System Instruction (包含 User Preference 與 Tool Context)
    prefs = db.query(UserPreference).filter(UserPreference.user_id == "default").all()
    instructions = ["你是一個有幫助的 AI 助手。"]
    for p in prefs:
        instructions.append(f"使用者的自訂偏好/記憶 ({p.settings_key}): {p.settings_value}")
    if tool_context:
        instructions.append(tool_context)
    
    system_instruction = "\n".join(instructions)

    # 取回歷史對話 (限定最近 20 筆避免爆 token)
    history_msgs = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id.desc()).limit(20).all()
    history_msgs.reverse()

    contents = []
    # 由於我們沒有真的把圖存進 gemini (若每次重新帶入圖片太消耗)，歷史訊息我們只帶文字
    for m in history_msgs[:-1]: # 除了剛存進去的 user_msg 外
        # Gemini 的 role: "user" 或 "model"
        r = m.role if m.role in ["user", "model"] else ("user" if m.role == "user" else "model")
        contents.append({"role": r, "parts": [m.content]})
    
    # 最新的這波對話 (包含照片)
    current_parts = []
    if has_attachment:
        image_bytes = await file.read()
        try:
            img = Image.open(BytesIO(image_bytes))
            # 轉換為 RGB 預防 RGBA 等問題
            if img.mode != 'RGB':
                img = img.convert('RGB')
            current_parts.append(img)
        except Exception as e:
            print(f"Image open error: {e}")
            pass
    if message:
        current_parts.append(message)
    contents.append({"role": "user", "parts": current_parts})

    # 設定 Model
    app_model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_instruction
    )

    # 自動產生標題 (針對新 Session)
    if session.title.startswith("New Chat"):
        try:
            title_res = app_model.generate_content(f"請用 5 個字以內總結這句話的主題：{message}")
            session.title = title_res.text.strip().replace('"', '').replace("'", "")
            db.commit()
        except:
            pass

    async def generate():
        full_text = ""
        try:
            response = app_model.generate_content(contents, stream=True)
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    chunk_json = json.dumps({"chunk": chunk.text})
                    yield f"data: {chunk_json}\n\n"
        except Exception as e:
            error_json = json.dumps({"error": str(e)})
            yield f"data: {error_json}\n\n"
        
        # 結束信號與儲存
        yield f"data: [DONE]\n\n"
        
        if full_text:
            ai_msg = Message(session_id=session_id, role="model", content=full_text, has_attachment=False)
            db.add(ai_msg)
            # 更新 session updated_at
            session.updated_at = datetime.utcnow()
            db.commit()

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/regenerate/{session_id}")
def regenerate_last(session_id: int, db: DBSession = Depends(get_db)):
    """刪除最後一筆 AI 訊息，並準備讓前端發送空的 POST /chat，這裡我們只要刪除就好"""
    last_msg = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id.desc()).first()
    if last_msg and last_msg.role == "model":
        db.delete(last_msg)
        db.commit()
        return {"status": "deleted_last_model_message"}
    return {"status": "no_model_message_to_delete"}
