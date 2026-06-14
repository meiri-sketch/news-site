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
gemini = genai.GenerativeModel("gemini-2.5-flash")
client = TelegramClient("session", TELEGRAM_API_ID, TELEGRAM_API_HASH)

def israel_time():
    return datetime.utcnow() + timedelta(hours=3)

async def fetch_all_messages(hours_back=2):
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
                    all_messages.append(f"[מקור: {name}]\n{msg.text.strip()}")
            print("נשלף: " + channel)
        except Exception as e:
            print("שגיאה: " + channel + " " + str(e))
    return all_messages

def summarize(messages):
    if not messages:
        return None, 0
    combined = "\n\n---\n\n".join(messages)
    prompt = """להלן הודעות מערוצי חדשות בטלגרם מהשעתיים האחרונות. כל הודעה מסומנת במקורה.

""" + combined + """

אנא צור סיכום חדשות בעברית לפי הכללים הבאים:
1. סדר את הידיעות לפי קטגוריות (למשל: ביטחוני, פוליטיקה, כלכלה, בינלאומי וכו') לפי ההקשר
2. כתוב כותרת לכל קטגוריה בשורה נפרדת מודגשת עם ** משני הצדדים
3. תחת כל קטגוריה כתוב את הידיעות, כל ידיעה מתחילה ב-•
4. בסוף כל ידיעה ציין את המקור בסוגריים, למשל: (עמית סגל)
5. אם כמה מקורות דיווחו על אותה ידיעה — אחד אותם לידיעה אחת וציין את כל המקורות
6. השמט תוכן פרסומי או ממומן לחלוטין"""

    response = gemini.generate_content(prompt)
    return response.text, len(messages)

def daily_summary(summaries):
    if len(summaries) < 2:
        return None
    recent = summaries[-8:]
    texts = [s["text"] for s in recent if s.get("count", 0) > 0]
    if not texts:
        return None
    combined = "\n\n---\n\n".join(texts)
    prompt = """להלן סיכומי חדשות מהשעות האחרונות:

""" + combined + """

צור תמצית קצרה של 3-5 נקודות עיקריות מכל השעות האחרונות בעברית. התחל כל נקודה ב-•"""
    try:
        response = gemini.generate_content(prompt)
        return response.text
    except:
        return None

def save_and_update(text, count, summaries_data):
    now = israel_time().isoformat()
    summaries_data["last_checked"] = now

    if text:
        summaries_data["summaries"].append({
            "timestamp": now,
            "text": text,
            "count": count
        })
        summaries_data["summaries"] = summaries_data["summaries"][-MAX_SUMMARIES:]

    digest = daily_summary(summaries_data["summaries"])
    if digest:
        summaries_data["digest"] = digest

    with open(SUMMARIES_FILE, "w", encoding="utf-8") as f:
        json.dump(summaries_data, f, ensure_ascii=False, indent=2)
    print("נשמר")

async def main():
    print("מריץ סיכום " + israel_time().strftime("%H:%M %d/%m/%Y"))

    try:
        with open(SUMMARIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {"summaries": [], "last_checked": "", "digest": ""}

    async with client:
        messages = await fetch_all_messages(2)
        print("נמצאו " + str(len(messages)) + " הודעות")

    text, count = summarize(messages)
    save_and_update(text, count, data)
    print("סיכום פורסם!")

asyncio.run(main())
