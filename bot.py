import requests
import time
import os
import threading
from flask import Flask

# ⚠️ کلیدها از متغیرهای محیطی بارگذاری می‌شوند.
BALE_TOKEN = os.environ.get('BALE_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# اگر کلیدها تنظیم نشده باشند، برنامه متوقف می‌شود.
if not BALE_TOKEN or not OPENROUTER_API_KEY:
    print("❌ خطای پیکربندی: BALE_TOKEN یا OPENROUTER_API_KEY در متغیرهای محیطی تنظیم نشده است.")
    # در محیط واقعی، بهتر است خطا داده شود. اما برای تست، می‌توان یک مقدار پیش‌فرض گذاشت.
    # در این مرحله، ترجیح می‌دهیم برنامه متوقف شود تا بعداً در Render تنظیمات را انجام دهیم.
    exit(1)

# 🔗 API URLs
BALE_BASE = f"https://tapi.bale.ai/bot{BALE_TOKEN}"
DEEPSEEK_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🌐 Flask app و متغیر جهانی برای آخرین آپدیت
app = Flask(__name__)
last_update_id = 0

@app.route("/")
def home():
    """نمایش وضعیت ربات"""
    return "🤖 Bale + GPT-3.5-Turbo Bot is Running (Ready for Deployment)"

# 💬 ارسال درخواست به مدل OpenRouter
def ask_deepseek(user_text: str) -> str:
    """ارسال متن کاربر به مدل GPT-3.5-Turbo از طریق OpenRouter"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": user_text}],
        "temperature": 0.7
    }
    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=45)
        resp.raise_for_status() 
        data = resp.json()

        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"].strip()

        error_message = data.get('error', {}).get('message', 'خطای ناشناخته در پاسخ مدل')
        return f"❌ خطای پاسخ مدل: {error_message}"

    except requests.exceptions.HTTPError as e:
        return f"❌ خطای HTTP در اتصال به OpenRouter: {e}. (کلید OpenRouter را در Render چک کنید)"
    except requests.exceptions.RequestException as e:
        return f"❌ خطای شبکه: {e}"
    except Exception as e:
        return f"❌ خطای پردازش پاسخ: {e}"

# 📥 گرفتن پیام‌های جدید از بله
def get_updates(offset: int | None) -> dict:
    """دریافت آپدیت‌های جدید از API بله"""
    params = {'offset': offset} if offset else {}
    try:
        res = requests.get(f"{BALE_BASE}/getUpdates", params=params, timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ خطای درخواست getUpdates از بله: {e}")
        return {}

# 📤 ارسال پاسخ به کاربر
def send_message(chat_id: int, reply_text: str):
    """ارسال پاسخ به کاربر در بله"""
    payload = {'chat_id': chat_id, 'text': reply_text}
    try:
        requests.post(f"{BALE_BASE}/sendMessage", json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"❌ خطای ارسال پیام به چت {chat_id}: {e}")

# 🤖 تابع اصلی اجرای ربات با polling
def run_bot():
    """حلقه اصلی Polling برای دریافت و پردازش پیام‌ها"""
    global last_update_id
    print("✅ ربات بله + OpenRouter فعال شد. در حال گوش دادن به پیام‌ها...")

    while True:
        try:
            updates = get_updates(last_update_id)
            
            for upd in updates.get("result", []):
                message = upd.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text")
                
                if chat_id and text:
                    print(f"[{chat_id}] 📩 پیام دریافت شد: {text}")
                    reply = ask_deepseek(text)
                    print(f"[{chat_id}] 📨 پاسخ آماده: {reply[:50]}...")
                    send_message(chat_id, reply)
                    
                current_update_id = upd.get("update_id", 0)
                if current_update_id >= last_update_id:
                     last_update_id = current_update_id + 1
            
            time.sleep(1)

        except Exception as e:
            print(f"🛑 خطای بحرانی در حلقه اصلی: {e}")
            time.sleep(5)

# 💡 اجرای بات در ترد جداگانه
def start_polling():
    """شروع حلقه Polling در یک Thread جداگانه"""
    threading.Thread(target=run_bot, daemon=True).start()

# 🚀 اجرای Flask Server
if __name__ == "__main__":
    start_polling()
    # پورت 10000 یا 5000 برای محیط‌های ابری رایج است.
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 سرور Flask در حال اجرا بر روی پورت {port}...")
    app.run(host="0.0.0.0", port=port)
