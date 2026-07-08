import asyncio
import json
import os
from datetime import datetime, timedelta
from telethon import TelegramClient
import google.generativeai as genai

TELEGRAM_API_ID = os.environ["TELEGRAM_API_ID"]
TELEGRAM_API_HASH = os.environ["TELEGRAM_API_HASH"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
CHANNELS = os.environ["CHANNELS"].split(",")

CHANNEL_NAMES = {
    "t.me/abualiexpress": "אבו עלי אקספרס",
    "t.me/amitsegal": "עמית סגל",
    "t.me/grinzaig": "אבישי גרינצייג",
}

MAX_SUMMARIES = 20
SUMMARIES_FILE = "summaries.json"

genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-2.5-flash-lite")
client = TelegramClient("session", TELEGRAM_API_ID, TELEGRAM_API_HASH)

def israel_time():
    return datetime.utcnow() + timedelta(hours=3)

async def fetch_all_messages(hours_back=1):
    since = datetime.utcnow() - timedelta(hours=hours_back)
    all_messages = []
    for channel in CHANNELS:
        channel = channel.strip()
        name = CHANNEL_NAMES.get(channel, channel)
        try:
            async for msg in client.iter_messages(channel, limit=100):
                if msg.date.replace(tzinfo=None) < since:
                    break
                if msg.text and len(msg.text.strip()) > 20:
                    all_messages.append("[מקור: " + name + "]\n" + msg.text.strip())
            print("נשלף: " + channel)
        except Exception as e:
            print("שגיאה: " + channel + " " + str(e))
    return all_messages

def build_prompt(combined):
    lines = [
        "להלן הודעות מערוצי חדשות בטלגרם מהשעה האחרונה. כל הודעה מסומנת במקורה.",
        "",
        combined,
        "",
        "אנא צור סיכום חדשות בעברית לפי הכללים הבאים:",
        "1. סדר את הידיעות לפי קטגוריות לפי ההקשר",
        "2. כתוב כותרת לכל קטגוריה מודגשת עם * משני הצדדים ושיהיה מודגש BOLD",
        "3. תחת כל קטגוריה כתוב את הידיעות, כל ידיעה מתחילה ב-*",
        "4. בסוף כל ידיעה ציין את המקור בסוגריים",
        "5. אם כמה מקורות דיווחו על אותה ידיעה - אחד אותם לידיעה אחת",
        "6. השמט תוכן פרסומי או ממומן",
        "7. התייחס רק לחדשות מהשעה האחרונה",
        "8. אל תוסיף שמות או פרטים שלא כתובים במפורש בטקסט המקורי",
    ]
    return "\n".join(lines)

def summarize(messages):
    if not messages:
        return None, 0
    combined = "\n\n---\n\n".join(messages)
    prompt = build_prompt(combined)
    response = gemini.generate_content(prompt)
    return response.text, len(messages)

def three_hour_digest(summaries):
    now = israel_time()
    cutoff = now - timedelta(hours=3)
    recent = []
    for s in summaries:
        try:
            ts = datetime.fromisoformat(s["timestamp"])
            if ts >= cutoff and s.get("count", 0) > 0:
                recent.append(s["text"])
        except:
            continue
    if not recent:
        return None
    combined = "\n\n---\n\n".join(recent)
    lines = [
        "להלן סיכומי חדשות מ-3 השעות האחרונות:",
        "",
        combined,
        "",
        "כתוב תקציר קצר של 2-3 שורות בלבד המסכם את הדברים החשובים ביותר. בלי כותרות, בלי בולטים.",
    ]
    prompt = "\n".join(lines)
    try:
        response = gemini.generate_content(prompt)
        return response.text.strip()
    except:
        return None

def save_and_update(text, count, summaries_data):
    now = israel_time().isoformat()
    summaries_data["last_checked"] = now
    digest = three_hour_digest(summaries_data["summaries"])
    if text:
        summaries_data["summaries"].append({
            "timestamp": now,
            "text": text,
            "count": count,
            "digest": digest
        })
        summaries_data["summaries"] = summaries_data["summaries"][-MAX_SUMMARIES:]
    with open(SUMMARIES_FILE, "w", encoding="utf-8") as f:
        json.dump(summaries_data, f, ensure_ascii=False, indent=2)
    print("נשמר")

async def main():
    print("מריץ סיכום " + israel_time().strftime("%H:%M %d/%m/%Y"))
    try:
        with open(SUMMARIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {"summaries": [], "last_checked": ""}
    async with client:
        messages = await fetch_all_messages(1)
        print("נמצאו " + str(len(messages)) + " הודעות")
    text, count = summarize(messages)
    save_and_update(text, count, data)
    print("סיכום פורסם!")

asyncio.run(main())
