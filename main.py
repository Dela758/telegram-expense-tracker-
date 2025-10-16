import logging
import os
import re
from datetime import datetime
from dotenv import load_dotenv

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

from utils import storage, parser
from utils.scheduler import schedule_jobs

logging.basicConfig(level=logging.INFO)

# Conversation states
ASK_PIN, VERIFY_PIN, ADD_EXPENSE, ADD_RECUR, SET_LIMIT, SET_BUDGET, SET_EMAIL, ASK_CURRENCY, ASK_EMAIL = range(9)

# -------------------- START / PIN --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Initialize new user
    if not storage.get_user_data(user_id):
        storage.save_user_data(user_id, {
            "expenses": [],
            "budget": 0,
            "currency": "USD",
            "pin": None,
            "category_limits": {},
            "email": None,
        })

        await update.message.reply_text(
            "👋 Welcome to *Expense Tracker Bot*! 🧾💸\n\n"
            "This bot helps you securely track expenses:\n"
            "✅ Add expenses\n"
            "✅ View summaries\n"
            "✅ Set budgets & limits\n"
            "✅ Upload receipts\n"
            "✅ Export monthly CSV to email\n\n"
            "Commands:\n"
            "/add - Add expense\n"
            "/recurring - Recurring expense\n"
            "/limit - Category limit\n"
            "/setbudget - Monthly budget\n"
            "/setemail - Save email\n"
            "/summary - Today’s summary\n"
            "/upload - Upload receipt\n"
            "/export - Export CSV\n"
            "/settings - Manage PIN, currency, preferences\n\n"
            "🔐 Set a 4-digit PIN to protect your data:",
            parse_mode="Markdown"
        )
        return ASK_PIN

    await update.message.reply_text(
        "👋 Welcome back! 🔐\n\n"
        "Please enter your 4-digit PIN to access your data.",
        parse_mode="Markdown"
    )
    return VERIFY_PIN

async def ask_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pin = update.message.text.strip()
    if not pin.isdigit() or len(pin) != 4:
        await update.message.reply_text("PIN must be 4 digits. Try again:")
        return ASK_PIN
    storage.set_user_pin(update.effective_user.id, pin)
    await update.message.reply_text("✅ PIN set! Start tracking expenses.")
    return ConversationHandler.END

async def verify_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pin = update.message.text.strip()
    if storage.validate_user_pin(update.effective_user.id, pin):
        await update.message.reply_text("🔓 Access granted! Use /add to log expenses.")
        return ConversationHandler.END
    await update.message.reply_text("❌ Incorrect PIN. Try again:")
    return VERIFY_PIN

# -------------------- EXPENSES --------------------

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parser.parse_expense_message(update.message.text)
    if not parsed:
        await update.message.reply_text("Couldn't understand. Try 'Spent 50 on food'")
        return
    user_id = update.effective_user.id
    user_data = storage.get_user_data(user_id)
    expenses = user_data.get("expenses", [])
    parsed["date"] = datetime.now().isoformat()
    expenses.append(parsed)
    user_data["expenses"] = expenses
    storage.save_user_data(user_id, user_data)
    await update.message.reply_text(f"💰 Added {parsed['amount']} for {parsed['category']}")

async def set_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send recurring expense like: 'Netflix 100'")
    return ADD_RECUR

async def save_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parser.parse_expense_message(update.message.text)
    if not parsed:
        await update.message.reply_text("Couldn’t parse. Try again.")
        return
    user_id = update.effective_user.id
    user_data = storage.get_user_data(user_id)
    rec = user_data.get("recurring", [])
    rec.append(parsed)
    user_data["recurring"] = rec
    storage.save_user_data(user_id, user_data)
    await update.message.reply_text("✅ Recurring expense saved.")
    return ConversationHandler.END

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send category limit like 'food 500'")
    return SET_LIMIT

async def save_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cat, amt = update.message.text.split()
        amt = float(amt)
    except:
        await update.message.reply_text("Format: category amount (e.g., food 500)")
        return
    user_id = update.effective_user.id
    data = storage.get_user_data(user_id)
    limits = data.get("category_limits", {})
    limits[cat.lower()] = amt
    data["category_limits"] = limits
    storage.save_user_data(user_id, data)
    await update.message.reply_text(f"✅ Limit set: {cat} → {amt} {data['currency']}")
    return ConversationHandler.END

async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter your monthly budget (e.g., 2000):")
    return SET_BUDGET

async def save_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        budget = float(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Invalid input. Please enter a number (e.g., 2000):")
        return SET_BUDGET
    user_id = update.effective_user.id
    data = storage.get_user_data(user_id)
    data["budget"] = budget
    storage.save_user_data(user_id, data)
    await update.message.reply_text(f"✅ Monthly budget set to {budget} {data['currency']}")
    return ConversationHandler.END

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = storage.get_user_data(user_id)
    expenses = user_data.get("expenses", [])
    if not expenses:
        await update.message.reply_text("No expenses recorded yet.")
        return
    today = datetime.now().date()
    total = sum(e['amount'] for e in expenses if datetime.fromisoformat(e['date']).date() == today)
    await update.message.reply_text(f"📊 Today: {total} {user_data['currency']}")

# -------------------- EMAIL / EXPORT --------------------

async def set_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter your email for monthly reports:")
    return SET_EMAIL

async def save_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text("Invalid email. Try again:")
        return
    user_id = update.effective_user.id
    user_data = storage.get_user_data(user_id)
    user_data["email"] = email
    storage.save_user_data(user_id, user_data)
    await update.message.reply_text("📩 Email saved.")
    return ConversationHandler.END

async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import csv
    from io import StringIO

    user_id = update.effective_user.id
    data = storage.get_user_data(user_id)
    expenses = data.get("expenses", [])
    if not expenses:
        await update.message.reply_text("No expenses to export.")
        return

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["date", "amount", "category", "description"])
    writer.writeheader()
    for item in expenses:
        writer.writerow(item)

    output.seek(0)
    await update.message.reply_document(document=output.getvalue().encode(), filename="expenses.csv")

# -------------------- PHOTOS --------------------

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Please send the receipt photo now.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text("❗ No photo received.")
        return
    photo = update.message.photo[-1]
    os.makedirs("receipts", exist_ok=True)
    path = f"receipts/{user_id}_receipt.jpg"
    file = await photo.get_file()
    await file.download_to_drive(path)
    await update.message.reply_text("🧾 Receipt saved.")

# -------------------- SETTINGS --------------------

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = storage.get_user_data(user_id) or {}
    current_currency = data.get("currency", "USD")

    keyboard = [
        [InlineKeyboardButton("🔐 Change PIN", callback_data='settings_pin')],
        [InlineKeyboardButton(f"💱 Change Currency (Current: {current_currency})", callback_data='settings_currency')],
        [InlineKeyboardButton("📧 Set/Change Email", callback_data='settings_email')],
        [InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ *Settings Menu:*", reply_markup=reply_markup, parse_mode="Markdown")

async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'settings_pin':
        await query.edit_message_text("🔐 Send new 4-digit PIN:")
        return ASK_PIN
    elif query.data == 'settings_currency':
        await query.edit_message_text("💱 Enter 3-letter currency code (e.g., USD, EUR, GHS):")
        return ASK_CURRENCY
    elif query.data == 'settings_email':
        await query.edit_message_text("📧 Enter your email address:")
        return ASK_EMAIL
    elif query.data == 'back_to_main':
        await query.edit_message_text("✅ Back to main. Use /add or /summary.")
        return ConversationHandler.END

async def received_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pin = update.message.text.strip()
    if not pin.isdigit() or len(pin) != 4:
        await update.message.reply_text("❌ Invalid PIN. Enter 4 digits:")
        return ASK_PIN
    user_id = update.effective_user.id
    data = storage.get_user_data(user_id) or {}
    data["pin"] = pin
    storage.save_user_data(user_id, data)
    await update.message.reply_text("✅ PIN updated.")
    return ConversationHandler.END

async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        await update.message.reply_text("❌ Invalid currency. Enter a 3-letter code:")
        return ASK_CURRENCY
    user_id = update.effective_user.id
    data = storage.get_user_data(user_id) or {}
    data["currency"] = currency
    storage.save_user_data(user_id, data)
    await update.message.reply_text(f"✅ Currency updated to {currency}.")
    return ConversationHandler.END

async def received_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if "@" not in email or "." not in email:
        await update.message.reply_text("❌ Invalid email. Enter again:")
        return ASK_EMAIL
    user_id = update.effective_user.id
    data = storage.get_user_data(user_id) or {}
    data["email"] = email
    storage.save_user_data(user_id, data)
    await update.message.reply_text(f"✅ Email updated to {email}.")
    return ConversationHandler.END

# -------------------- MAIN --------------------

load_dotenv()
if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    # Conversations
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pin)],
            VERIFY_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_pin)]
        },
        fallbacks=[]
    )

    recur_conv = ConversationHandler(
        entry_points=[CommandHandler("recurring", set_recurring)],
        states={ADD_RECUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_recurring)]},
        fallbacks=[]
    )

    limit_conv = ConversationHandler(
        entry_points=[CommandHandler("limit", set_limit)],
        states={SET_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_limit)]},
        fallbacks=[]
    )

    budget_conv = ConversationHandler(
        entry_points=[CommandHandler("setbudget", set_budget)],
        states={SET_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_budget)]},
        fallbacks=[]
    )

    email_conv = ConversationHandler(
        entry_points=[CommandHandler("setemail", set_email)],
        states={SET_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_email)]},
        fallbacks=[]
    )

    settings_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("settings", settings),
            CallbackQueryHandler(settings_callback_handler)
        ],
        states={
            ASK_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_currency)],
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_email)],
            ASK_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_pin)],
        },
        fallbacks=[],
        name="settings_conversation",
        persistent=False,
    )

    # Register handlers
    app.add_handler(conv)
    app.add_handler(recur_conv)
    app.add_handler(limit_conv)
    app.add_handler(budget_conv)
    app.add_handler(email_conv)
    app.add_handler(settings_conv_handler)
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("export", export_csv))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense))

    # Start background jobs
    schedule_jobs(app.bot)

    app.run_polling()
