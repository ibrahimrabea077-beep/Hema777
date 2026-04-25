# Hema AI Backend

مساعد ذكي باستخدام Grok من xAI مع Web Search + Code Execution.

## رفع على Render
- أضف Environment Variable: `XAI_API_KEY`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`