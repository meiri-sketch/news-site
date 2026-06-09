"""
Telegram News Summarizer — Gemini + GitHub Pages
שולף חדשות מטלגרם, מסכם עם Gemini, ומעלה לדף ווב
"""

import asyncio
import schedule
import time
import json
import os
import subprocess
from datetime import datetime, timedelta
from telethon import TelegramClient
import google.generativeai as genai

# ─── הגדרות ───────────────────────────────────────────────────────────────────
TELEGRAM_API_ID    = "YOUR_API_ID"
TELEGRAM_API_HASH  = "YOUR_API_HASH"
CHANNEL_USERNAME   = "channel_username"     # ללא @

GEMINI_API_KEY     = "YOUR_GEMINI_KEY"

# GitHub
GITHUB_USERNAME    = "YOUR_GITHUB_USERNAME"
GITHUB_REPO        = "news-site"            # שם הריפו שתיצור
GITHUB_TOKEN       = "YOUR_GITHUB_TOKEN"    # Personal Access Token

HOURS_INTERVAL     = 6
MAX_SUMMARIES      = 20                     # כמה סיכומים לשמור בהיסטוריה
REPO_PATH          = r"C:\Users\YOUR_USER\news-site"  # תיקיית הריפו המקומית
# ─────────────────────────────────────────────────────────────────────────────

genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel("gemini-1.5-flash")
client = TelegramClient("session", TELEGRAM_API_ID, TELEGRAM_API_HASH)
SUMMARIES_FILE = os.path.join(REPO_PATH, "summaries.json")


async def fetch_messages(hours_back: int = 6) -> list[str]:
    since = datetime.utcnow() - timedelta(hours=hours_back)
    messages = []
    async for msg in client.iter_messages(CHANNEL_USERNAME, limit=200):
        if msg.date.replace(tzinfo=None) < since:
            break
        if msg.text and len(msg.text.strip()) > 20:
            messages.append(msg.text.strip())
    return list(reversed(messages))


def summarize(messages: list[str]) -> tuple[str, int]:
    if not messages:
        return "לא פורסמו חדשות ב-6 השעות האחרונות.", 0

    combined = "\n\n---\n\n".join(messages)
    prompt = f"""להלן הודעות מערוץ חדשות בטלגרם מ-6 השעות האחרונות:

{combined}

אנא צור סיכום חדשות תמציתי בעברית:
• הידיעות העיקריות (3-7 נקודות)
• כל נקודה תתחיל בתו • 
• כתוב בצורה ברורה ותמציתית"""

    response = gemini.generate_content(prompt)
    return response.text, len(messages)


def save_summary(text: str, count: int):
    """שומר את הסיכום ל-JSON"""
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

    # שמור רק N האחרונים
    data["summaries"] = data["summaries"][-MAX_SUMMARIES:]

    with open(SUMMARIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"💾 נשמר ל-{SUMMARIES_FILE}")


def push_to_github():
    """דוחף את הקבצים ל-GitHub Pages"""
    try:
        os.chdir(REPO_PATH)
        subprocess.run(["git", "add", "summaries.json"], check=True)
        subprocess.run(["git", "commit", "-m", f"update: {datetime.now().strftime('%H:%M %d/%m/%Y')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🌐 הועלה ל-GitHub Pages")
    except subprocess.CalledProcessError as e:
        print(f"❌ שגיאת Git: {e}")


async def run_summary():
    print(f"\n🕐 מריץ סיכום — {datetime.now().strftime('%H:%M %d/%m/%Y')}")

    async with client:
        messages = await fetch_messages(HOURS_INTERVAL)
        print(f"📨 נמצאו {len(messages)} הודעות")

    text, count = summarize(messages)
    save_summary(text, count)
    push_to_github()
    print(f"✅ הסיכום פורסם בדף!")


def job():
    asyncio.run(run_summary())


if __name__ == "__main__":
    print("🚀 מתחיל...")
    job()

    schedule.every(HOURS_INTERVAL).hours.do(job)
    print(f"⏱️  מתוזמן לכל {HOURS_INTERVAL} שעות. Ctrl+C לעצירה.")

    while True:
        schedule.run_pending()
        time.sleep(60)
