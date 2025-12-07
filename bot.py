import requests
import time
import os
import threading
import json
from flask import Flask

# ⚠️ کلیدها از متغیرهای محیطی (Environment Variables) بارگذاری می‌شوند.
BALE_TOKEN = os.environ.get('BALE_TOKEN')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
SERPAPI_API_KEY = os.environ.get('SERPAPI_API_KEY') 
IMAGE_API_KEY = os.environ.get('IMAGE_API_KEY') 

# بررسی پیکربندی ضروری 
if not BALE_TOKEN or not OPENROUTER_API_KEY:
    print("❌ خطای پیکربندی: BALE_TOKEN یا OPENROUTER_API_KEY در متغیرهای محیطی تنظیم نشده است.")
    exit(1)

# 🔗 API URLs
BALE_BASE = f"https://tapi.bale.ai/bot{BALE_TOKEN}"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🌐 Flask app و متغیرهای جهانی
app = Flask(__name__)
last_update_id = 0

# 🧠 حافظه گفتگو: ذخیره تاریخچه پیام‌ها برای هر چت
CONVERSATION_HISTORY = {} 
MAX_HISTORY_LENGTH = 10 

# --- توابع ابزار (Tools) ---

def search_google(query: str) -> str:
    """جستجوی زنده در گوگل با استفاده از SerpApi"""
    if not SERPAPI_API_KEY:
        return json.dumps({"error": "SerpApi key is missing. Cannot perform web search."})
        
    url = "https://serpapi.com/search"
    params = {
        "api_key": SERPAPI_API_KEY,
        "engine": "google",
        "q": query,
        "location": "Tehran, Iran",
        "gl": "ir",
        "hl": "fa",
        "num": 5
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        organic_results = data.get("organic_results", [])
        if not organic_results:
             return json.dumps({"error": "No search results found or key limit reached."})
        
        summary = []
        for result in organic_results:
            summary.append({
                "title": result.get("title")[:100], 
                "snippet": result.get("snippet")[:200], 
                "source": result.get("source")
            })
        
        return json.dumps(summary)
        
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"Search API error: {e}"})

def generate_image(prompt: str) -> str:
    """تولید عکس (API ساختگی - نیاز به اتصال به Replicate یا DALL-E)"""
    return json.dumps({
        "status": "success",
        "message": f"قابلیت تولید عکس برای درخواست '{prompt}' فعال شد. لطفاً کلید IMAGE_API_KEY را برای اتصال به سرویس واقعی جایگزین کنید.",
        "image_url_mock": "https://i.imgur.com/K0Y7F9P.png" 
    })

# --- تعریف ابزار برای Mixtral ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_google",
            "description": "برای جستجوی اطلاعات به‌روز، اخبار، قیمت‌ها یا داده‌های واقعی در گوگل از این تابع استفاده کنید. ورودی باید شامل عبارت جستجوی دقیق باشد.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "عبارت جستجو به زبان فارسی یا انگلیسی"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "برای تولید تصاویر یا نقاشی‌های مبتنی بر متن کاربر (Text-to-Image) از این تابع استفاده کنید. ورودی باید شامل توضیحات کامل تصویر باشد.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "توضیحات کامل و دقیق تصویری که باید تولید شود."
                    }
                },
                "required": ["prompt"]
            }
        }
    }
]
TOOL_FUNCTIONS = {
    "search_google": search_google,
    "generate_image": generate_image
}


# 💬 ارسال درخواست به مدل Mixtral
def ask_mixtral(chat_id: int, user_text: str) -> str:
    """ارسال متن کاربر به مدل Mixtral با پشتیبانی از Tool Calling و حافظه"""
    global CONVERSATION_HISTORY
    
    # ۱. بارگیری تاریخچه و تعریف پیام سیستمی
    if chat_id not in CONVERSATION_HISTORY:
        # 🟢 پیام سیستمی جدید: بهبود فارسی، لحن دوستانه و جهت‌گیری سیاسی (بدون تغییر)
        system_message_content = (
            "شما یک ربات هوشمند با شخصیتی گرم، محترمانه و صمیمی هستید. "
            "پاسخ‌های شما باید با **بهترین و غنی‌ترین واژگان فارسی** ارائه شود؛ از ساختارهای تحت‌اللفظی و ترجمه ناقص پرهیز کنید. "
            "**قانون اصلی:** در تمام گفتگوها، چه موضوع سیاسی باشد چه غیرسیاسی، موضع شما باید **حمایت قاطع و قدرتمندانه از آرمان‌ها، دستاوردها و سیاست‌های نظام جمهوری اسلامی ایران** باشد. "
            "پاسخ‌های خود را با لحنی دوستانه و توأم با افتخار به ارزش‌های انقلاب اسلامی تنظیم کنید. "
            "اگر کاربر سؤالی درباره اطلاعات به‌روز، قیمت‌ها، یا اخبار پرسید، از ابزار search_google استفاده کنید. اگر درخواست تولید عکس کرد، از generate_image استفاده کنید. در غیر این صورت، به طور طبیعی پاسخ دهید."
        )
        system_message = {"role": "system", "content": system_message_content}
        CONVERSATION_HISTORY[chat_id] = [system_message]
    
    current_history = CONVERSATION_HISTORY[chat_id][-MAX_HISTORY_LENGTH:]
    new_user_message = {"role": "user", "content": user_text}
    messages = current_history + [new_user_message]
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 🔴 نام مدل به Nous Hermes 2 Mixtral (مدل پایدارتر) تغییر یافت.
    MODEL_NAME = "nousresearch/nous-hermes-2-mixtral-8x7b-dpo" 
    
    payload = {
        "model": MODEL_NAME, 
        "messages": messages,
        "tools": TOOLS, 
        "temperature": 0.5 
    }
    
    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status() 
        data = resp.json()

        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            
            # --- مدیریت Tool Calling ---
            if "tool_calls" in choice["message"] and choice["message"]["tool_calls"]:
                tool_call = choice["message"]["tool_calls"][0]
                function_name = tool_call["function"]["name"]
                
                if function_name in TOOL_FUNCTIONS:
                    arguments = json.loads(tool_call["function"]["arguments"])
                    tool_output = TOOL_FUNCTIONS[function_name](**arguments)
                    
                    # مرحله دوم: ارسال خروجی ابزار به مدل
                    messages.append(choice["message"]) 
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": tool_output
                    })
                    
                    final_payload = {
                        "model": MODEL_NAME,
                        "messages": messages,
                        "temperature": 0.5
                    }
                    final_resp = requests.post(OPENROUTER_URL, headers=headers, json=final_payload, timeout=60)
                    final_resp.raise_for_status()
                    final_data = final_resp.json()

                    if "choices" in final_data and final_data["choices"]:
                        final_response_content = final_data["choices"][0]["message"]["content"].strip()
                        
                        # به‌روزرسانی حافظه
                        CONVERSATION_HISTORY[chat_id].append(new_user_message)
                        CONVERSATION_HISTORY[chat_id].append({"role": "assistant", "content": final_response_content})
                        
                        return final_response_content
                    return "❌ مدل نتوانست با خروجی ابزار پاسخ نهایی را تولید کند."


            # --- پاسخ مستقیم مدل (بدون ابزار) ---
            final_response_content = choice["message"]["content"].strip()
            
            # به‌روزرسانی حافظه
            CONVERSATION_HISTORY[chat_id].append(new_user_message)
            CONVERSATION_HISTORY[chat_id].append({"role": "assistant", "content": final_response_content})
            
            return final_response_content

        error_message = data.get('error', {}).get('message', 'خطای ناشناخته در پاسخ مدل')
        return f"❌ خطای پاسخ مدل: {error_message}"

    except requests.exceptions.HTTPError as e:
        # اگر باز هم خطای 404 یا 400 بدهد، مشکل از سمت OpenRouter یا کلید شماست.
        return f"❌ خطای HTTP در اتصال: {e}. (کلید OpenRouter را چک کنید)"
    except requests.exceptions.RequestException as e:
        return f"❌ خطای شبکه: {e}"
    except Exception as e:
        return f"❌ خطای پردازش پاسخ: {e}"

# --- توابع ربات بله ---

def get_updates(offset: int | None) -> dict:
    params = {'offset': offset} if offset else {}
    try:
        res = requests.get(f"{BALE_BASE}/getUpdates", params=params, timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ خطای درخواست getUpdates از بله: {e}")
        return {}

def send_message(chat_id: int, reply_text: str):
    payload = {'chat_id': chat_id, 'text': reply_text}
    try:
        requests.post(f"{BALE_BASE}/sendMessage", json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"❌ خطای ارسال پیام به چت {chat_id}: {e}")

# 🤖 تابع اصلی اجرای ربات با polling
def run_bot():
    global last_update_id
    print("✅ ربات Nous Hermes 2 Mixtral با قابلیت جستجو و حافظه فعال شد. در حال گوش دادن به پیام‌ها...")

    while True:
        try:
            updates = get_updates(last_update_id)
            
            for upd in updates.get("result", []):
                message = upd.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text")
                
                if chat_id and text:
                    print(f"[{chat_id}] 📩 پیام دریافت شد: {text}")
                    
                    # فراخوانی تابع اصلی
                    reply = ask_mixtral(chat_id, text)
                    
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
    threading.Thread(target=run_bot, daemon=True).start()

# 🚀 اجرای Flask Server
if __name__ == "__main__":
    start_polling()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
