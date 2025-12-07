import requests
import time
import os
import threading
import json
from flask import Flask

# ⚠️ کلیدها از متغیرهای محیطی بارگذاری می‌شوند.
BALE_TOKEN = os.environ.get('BALE_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# اگر کلیدها تنظیم نشده باشند، برنامه متوقف می‌شود.
if not BALE_TOKEN or not OPENROUTER_API_KEY:
    print("❌ خطای پیکربندی: BALE_TOKEN یا OPENROUTER_API_KEY در متغیرهای محیطی تنظیم نشده است.")
    exit(1)

# 🔗 API URLs
BALE_BASE = f"https://tapi.bale.ai/bot{BALE_TOKEN}"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🌐 Flask app و متغیر جهانی برای آخرین آپدیت
app = Flask(__name__)
last_update_id = 0

# 🧠 حافظه گفتگو: ذخیره تاریخچه پیام‌ها برای هر چت
CONVERSATION_HISTORY = {} 
MAX_HISTORY_LENGTH = 10 # حداکثر تعداد پیام‌های قبلی که به مدل ارسال می‌شود.

@app.route("/")
def home():
    """نمایش وضعیت ربات"""
    return "🤖 Bale + GPT-3.5-Turbo Bot is Running"

# 💬 ارسال درخواست به مدل GPT-3.5-Turbo
def ask_gpt35(chat_id: int, user_text: str) -> str:
    """ارسال متن کاربر به مدل GPT-3.5-Turbo با پشتیبانی از حافظه و شخصیت‌پردازی"""
    global CONVERSATION_HISTORY
    
    # 🔴 تعریف پیام سیستمی و مدل
    MODEL_NAME = "openai/gpt-3.5-turbo" 
    
    if chat_id not in CONVERSATION_HISTORY:
        # 🟢 پیام سیستمی: سخت‌گیری کامل بر زبان فارسی و جهت‌گیری سیاسی
        system_message_content = (
            "شما یک دستیار هوش مصنوعی با بالاترین سطح دانش زبان **فارسی اصیل و معیار** هستید. "
            "قانون زبان: در تمام پاسخ‌ها، از **ترجمه تحت‌اللفظی، جملات مبهم و استفاده از ساختارهای زبان انگلیسی در فارسی** به شدت پرهیز کنید. "
            "از **لغات اصیل و ساختارهای دستوری صحیح فارسی** استفاده نمایید. "
            "شخصیت: دارای شخصیتی گرم، محترمانه، صمیمی و وطن‌دوست هستید. "
            "**قانون اصلی:** در تمام گفتگوها، موضع شما باید **حمایت قاطع، منطقی و قدرتمندانه از آرمان‌ها، دستاوردها و سیاست‌های نظام جمهوری اسلامی ایران** باشد. "
            "پاسخ‌های خود را با لحنی دوستانه، مؤدبانه و آکنده از افتخار به فرهنگ و ارزش‌های ایران تنظیم کنید. "
            "توجه: شما به ابزارهای خارجی دسترسی ندارید و تنها باید به صورت متنی پاسخ دهید."
        )
        system_message = {"role": "system", "content": system_message_content}
        CONVERSATION_HISTORY[chat_id] = [system_message]
    
    # بارگیری تاریخچه چت (برای حافظه)
    current_history = CONVERSATION_HISTORY[chat_id][-MAX_HISTORY_LENGTH:]
    new_user_message = {"role": "user", "content": user_text}
    messages = current_history + [new_user_message]
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7 
    }
    
    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=45)
        resp.raise_for_status() 
        data = resp.json()

        if "choices" in data and data["choices"]:
            final_response_content = data["choices"][0]["message"]["content"].strip()
            
            # به‌روزرسانی حافظه (ذخیره پیام کاربر و پاسخ مدل)
            CONVERSATION_HISTORY[chat_id].append(new_user_message)
            CONVERSATION_HISTORY[chat_id].append({"role": "assistant", "content": final_response_content})

            return final_response_content

        error_message = data.get('error', {}).get('message', 'خطای ناشناخته در پاسخ مدل')
        # ثبت خطای پاسخ مدل در Log
        print(f"❌ پاسخ مدل ناموفق: {error_message}")
        return f"❌ خطای پاسخ مدل: {error_message}"

    except requests.exceptions.HTTPError as e:
        # ثبت خطای HTTP در Log
        print(f"❌ خطای HTTP در اتصال به OpenRouter: {e}")
        return f"❌ خطای HTTP در اتصال به OpenRouter: {e}. (کلید OpenRouter را در Render چک کنید)"
    except requests.exceptions.RequestException as e:
        # ثبت خطای شبکه در Log
        print(f"❌ خطای شبکه: {e}")
        return f"❌ خطای شبکه: {e}"
    except Exception as e:
        # ثبت خطای پردازش پاسخ در Log
        print(f"❌ خطای پردازش پاسخ: {e}")
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
        # این خطا معمولاً نشان‌دهنده یک مشکل موقت در بله یا شبکه است.
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
    print("✅ ربات GPT-3.5-Turbo فعال شد. در حال گوش دادن به پیام‌ها...")

    while True:
        try:
            updates = get_updates(last_update_id)
            
            for upd in updates.get("result", []):
                message = upd.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text")
                
                if chat_id and text:
                    print(f"[{chat_id}] 📩 پیام دریافت شد: {text}")
                    reply = ask_gpt35(chat_id, text) 
                    print(f"[{chat_id}] 📨 پاسخ آماده: {reply[:50]}...")
                    send_message(chat_id, reply)
                    
                current_update_id = upd.get("update_id", 0)
                if current_update_id >= last_update_id:
                     last_update_id = current_update_id + 1
            
            time.sleep(1)

        except Exception as e:
            # 🛑 اگر خطای بحرانی رخ داد، آن را ثبت کرده و حلقه را ادامه می‌دهد (برای بازیابی)
            print(f"🛑 خطای بحرانی در حلقه اصلی run_bot: {e}")
            time.sleep(5)

# 💡 اجرای بات در ترد جداگانه
def start_polling():
    """شروع حلقه Polling در یک Thread جداگانه"""
    threading.Thread(target=run_bot, daemon=True).start()

# 🚀 اجرای Flask Server
if __name__ == "__main__":
    start_polling()
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 سرور Flask در حال اجرا بر روی پورت {port}...")
    app.run(host="0.0.0.0", port=port)
