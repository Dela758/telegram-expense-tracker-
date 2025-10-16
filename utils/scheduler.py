import schedule
import threading
import time
import asyncio
import os
from datetime import datetime
from . import storage, mailer
from telegram import Bot

# Daily summary
async def send_daily_summary(bot: Bot, user_id, chat_id):
    data = storage.get_user_data(user_id)
    if not data:
        return
    today = datetime.now().date().isoformat()
    summary = sum(e['amount'] for e in data.get('expenses', []) if e['date'].startswith(today))
    await bot.send_message(chat_id, f"📊 Today's total: {summary:.2f}")

# Category limit checks
async def check_limits(bot: Bot, user_id, chat_id):
    data = storage.get_user_data(user_id)
    if not data:
        return
    limits = data.get("limits", {})
    total = {}
    for e in data.get("expenses", []):
        cat = e['category']
        total[cat] = total.get(cat, 0) + e['amount']
    warnings = []
    for cat, amt in total.items():
        if cat in limits and amt > limits[cat]:
            warnings.append(f"⚠️ {cat} overspent by {amt - limits[cat]:.2f}")
    if warnings:
        await bot.send_message(chat_id, "\n".join(warnings))

# Monthly email report
async def send_monthly_report(bot: Bot, user_id, chat_id):
    data = storage.get_user_data(user_id)
    if not data:
        return
    email = data.get("email")
    if email:
        try:
            path = mailer.export_csv(user_id, data.get("expenses", []))
            mailer.send_email(email, path)
            await bot.send_message(chat_id, f"📧 Monthly report sent to {email}")
        except Exception as e:
            print(f"[ERROR] Failed to send report for {user_id}: {e}")

# Main scheduler runner
def run_schedule(bot: Bot):
    user_files = [
        f for f in os.listdir("data")
        if f.endswith(".json") and f != "encrypted_data.json" and not f.startswith("keys/")
    ]

    for file in user_files:
        user_id = file.replace(".json", "")
        try:
            chat_id = int(user_id)
        except ValueError:
            print(f"Skipping file: {file} (not a user ID)")
            continue

        data = storage.get_user_data(user_id)
        if not data:
            continue  # Skip corrupted or unreadable files

        schedule.every().day.at("20:00").do(lambda uid=user_id, cid=chat_id:
            asyncio.run(send_daily_summary(bot, uid, cid)))
        schedule.every().day.at("20:05").do(lambda uid=user_id, cid=chat_id:
            asyncio.run(check_limits(bot, uid, cid)))
        if datetime.now().day == 1:
            asyncio.run(send_monthly_report(bot, user_id, chat_id))

def run():
    while True:
        schedule.run_pending()
        time.sleep(60)

def schedule_jobs(bot):
    threading.Thread(target=run_schedule, args=(bot,), daemon=True).start()
