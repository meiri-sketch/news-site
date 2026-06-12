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

MAX_SUMMARIES = 20
SUMMARIES_FILE = "summaries.json"

genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-2.5-flash")
client = TelegramClient("session", TELEGRAM_API_ID, TELEGRAM_API_HASH)


async def fetch_all_messages(hours_back=1):
    since = datetime.utcnow() - timedelta(hours=hours_back)
    all_messages = []
    for channel in CHANNELS:
        try:
            async for msg in client.iter_messages(channel.strip(), limit=100):
                if msg.date.replace(tzinfo=None) < since:
                    break
                if msg.text and len(msg.text.strip()) > 20:
                    all_messages.append(msg.text.strip())
            print("נשלף: " + channel)
        except Exception as e:
            print("שגיאה: " + channel + " " + str(e))
    return all_messages


def summarize(messages):
    if not messages:
        return "לא פורסמו חדשות בשעה האחרונה.", 0
    combined = "\n\n---\n\n".join(messages)
    prompt = "להלן הודעות מערוצי חדשות בטלגרם מהשעה האחרונה:\n\n" + combined + "\n\nצור סיכום חדשות תמציתי בעברית. כל נקודה תתחיל ב-•"
    response = gemini.generate_content(prompt)
    return response.text, len(messages)


def save_summary(text, count):
    try:
        with open(SUMMARIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {"summaries": []}
    data["summaries"].append({
        "timestamp": datetime.now().isoformat(),
        "text": text,
        "count": count
    })
    data["summaries"] = data["summaries"][-MAX_SUMMARIES:]
    with open(SUMMARIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("נשמר")


async def main():
    print("מריץ סיכום " + datetime.now().strftime("%H:%M %d/%m/%Y"))
    async with client:
        messages = await fetch_all_messages(1)
        print("נמצאו " + str(len(messages)) + " הודעות")
    text, count = summarize(messages)
    save_summary(text, count)
    print("סיכום פורסם!")


asyncio.run(main())
