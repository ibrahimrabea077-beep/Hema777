from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
import os
import json
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Hema AI - Powered by Grok (Web Search + Code Execution)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

import sqlite3
conn = sqlite3.connect("hema_history.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT,
    content TEXT,
    timestamp TEXT,
    tools_used TEXT DEFAULT NULL
)
""")
conn.commit()

class ChatRequest(BaseModel):
    message: str
    use_tools: bool = True

SYSTEM_PROMPT = """
أنت Hema، مساعد ذكي وقوي جداً مبني على Grok من xAI.
لديك أدوات مدمجة:
- web_search: بحث على الإنترنت في الوقت الفعلي.
- code_execution: تنفيذ كود Python آمن (حسابات، رسوم بيانية، تحليل بيانات...).

استخدم الأدوات تلقائياً عند الحاجة.
كن مفيداً ودقيقاً، ورد بالعربية أو الإنجليزية حسب اليوزر.
"""

@app.post("/chat")
async def chat_with_tools(req: ChatRequest):
    try:
        cursor.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT 30")
        history_rows = cursor.fetchall()[::-1]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for role, content in history_rows:
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": req.message})

        tools = [{"type": "web_search"}, {"type": "code_execution"}] if req.use_tools else None

        async def stream_response():
            full_reply = ""
            stream = client.chat.completions.create(
                model="grok-4.20-reasoning",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.7,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta

                if delta.content:
                    content = delta.content
                    full_reply += content
                    yield f"data: {json.dumps({'type': 'content', 'delta': content})}\n\n"

                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tc in delta.tool_calls:
                        tool_name = getattr(tc.function, 'name', 'tool') if hasattr(tc, 'function') else 'tool'
                        yield f"data: {json.dumps({'type': 'tool_use', 'message': f'🔧 جاري استخدام {tool_name}...'})} \n\n"

            now = datetime.now().isoformat()
            tools_str = "web_search + code_execution" if req.use_tools else "none"
            cursor.execute("INSERT INTO messages (role, content, timestamp, tools_used) VALUES (?, ?, ?, ?)", 
                          ("user", req.message, now, tools_str))
            cursor.execute("INSERT INTO messages (role, content, timestamp, tools_used) VALUES (?, ?, ?, ?)", 
                          ("assistant", full_reply, now, tools_str))
            conn.commit()

            yield f"data: {json.dumps({'type': 'done', 'full_reply': full_reply})}\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ: {str(e)}")

@app.get("/history")
async def get_history():
    cursor.execute("SELECT id, role, content, timestamp, tools_used FROM messages ORDER BY id")
    rows = cursor.fetchall()
    return [{"id": r[0], "role": r[1], "content": r[2], "timestamp": r[3], "tools_used": r[4]} for r in rows]

@app.delete("/history")
async def clear_history():
    cursor.execute("DELETE FROM messages")
    conn.commit()
    return {"status": "success", "message": "تم مسح التاريخ بنجاح"}

@app.get("/")
async def root():
    return {"message": "Hema AI Backend شغال ✅ - Powered by Grok"}