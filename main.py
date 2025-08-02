import os
import requests
import time
from flask import Flask
import threading

# 🔐 تنظیمات اولیه
BALE_TOKEN = '150525664:fs6SMNT7DGTJDEFujcK4ABnP5rgeOUpzi4BzXYEB'
OPENROUTER_API_KEY = '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'
BALE_BASE = f"https://tapi.bale.ai/bot{BALE_TOKEN}"
DEEPSEEK_URL = "https://openrouter.ai/api/v1/chat/completions"

# ایجاد اپلیکیشن Flask
app = Flask(__name__)

# تابع ارسال پیام به مدل DeepSeek
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

# تابع دریافت به‌روزرسانی‌ها از بله
def get_updates(offset=None):
    try:
        res = requests.get(f"{BALE_BASE}/getUpdates", params={'offset': offset}, timeout=10)
        return res.json()
    except Exception as e:
        print("❌ خطا دریافت پیام:", e)
        return {}

# تابع ارسال پیام به چت
def send_message(chat_id, reply_text):
    try:
        requests.post(f"{BALE_BASE}/sendMessage", json={'chat_id': chat_id, 'text': reply_text}, timeout=10)
    except Exception as e:
        print("❌ خطا ارسال پیام:", e)

# تابع اصلی برای اجرای ربات
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

# روت اصلی که به پورت گوش می‌ده
@app.route("/")
def home():
    return "Bot is running!"

# اجرای ربات در یک ترد جداگانه
def start_polling():
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    # اجرای ترد برای polling و شروع سرور Flask
    start_polling()
    
    # پورت مناسب را از متغیر محیطی می‌گیریم
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)