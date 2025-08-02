import os
import requests
import time
from flask import Flask
import threading

# ❗ کلیدها مستقیماً داخل کد (برای تست فقط)
BALE_TOKEN = os.environ.get('BALE_TOKEN')
OPENROUTER_API_KEY = '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'

BALE_BASE = f"https://tapi.bale.ai/bot{BALE_TOKEN}"
DEEPSEEK_URL = "https://openrouter.ai/api/v1/chat/completions"

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ ربات بله + DeepSeek روی Render فعال است."

def ask_deepseek(user_text):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [{"role": "user", "content": user_text}],
        "temperature": 0.7
    }
    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        data = resp.json()
        if 'error' in data:
            return f"❌ خطا از مدل: {data['error'].get('message', '')}"
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"].strip()
        return f"❌ پاسخ نامعتبر: {data}"
    except Exception as e:
        return f"❌ اتصال به DeepSeek با خطا: {e}"

def get_updates(offset=None):
    try:
        res = requests.get(f"{BALE_BASE}/getUpdates", params={'offset': offset}, timeout=10)
        return res.json()
    except Exception as e:
        print("❌ خطا دریافت پیام:", e)
        return {}

def send_message(chat_id, reply_text):
    try:
        requests.post(f"{BALE_BASE}/sendMessage", json={'chat_id': chat_id, 'text': reply_text}, timeout=10)
    except Exception as e:
        print("❌ خطا ارسال پیام:", e)

def run_bot():
    offset = None
    print("🤖 ربات هوشمند بله با DeepSeek‑R1 فعال شد")
    while True:
        updates = get_updates(offset)
        for upd in updates.get("result", []):
            msg = upd.get("message", {})
            cid = msg.get("chat", {}).get("id")
            text = msg.get("text")
            if cid and text:
                print("📩 کاربر گفت:", text)
                reply = ask_deepseek(text)
                print("📨 پاسخ مدل:", reply)
                send_message(cid, reply)
            offset = upd.get("update_id", 0) + 1
        time.sleep(1)

def start_polling():
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    start_polling()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)