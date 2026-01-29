import sqlite3
import uuid
import threading
import requests
from flask import Flask, request, jsonify

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================== CONFIG ==================

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
NOWPAY_API_KEY = "YOUR_NOWPAY_API_KEY"

COINS_PER_TASK = 1.7

# ================== DATABASE ==================

def init_db():
    conn = sqlite3.connect("bot.db", check_same_thread=False)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            coins REAL DEFAULT 0
        )
    """)

    conn.commit()
    return conn


db = init_db()

# ================== FLASK (IPN / WEBHOOKS) ==================

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is running"

@app_web.route("/ipn", methods=["POST"])
def ipn():
    data = request.json
    print("IPN RECEIVED:", data)
    return jsonify({"status": "ok"}), 200


# ================== PAYMENTS ==================

def create_invoice(amount, description):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "price_amount": amount,
        "price_currency": "usd",
        "pay_currency": "btc",
        "order_id": str(uuid.uuid4()),
        "order_description": description,
    }

    r = requests.post(url, json=payload, headers=headers, timeout=20)
    return r.json()


# ================== HELPERS ==================

def get_user(user_id):
    cur = db.cursor()
    cur.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    if row is None:
        cur.execute(
            "INSERT INTO users (user_id, coins) VALUES (?, ?)",
            (user_id, 0),
        )
        db.commit()
        return 0

    return row[0]


def add_coins(user_id, amount):
    cur = db.cursor()
    cur.execute(
        "UPDATE users SET coins = coins + ? WHERE user_id = ?",
        (amount, user_id),
    )
    db.commit()


# ================== BOT COMMANDS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins = get_user(user.id)

    keyboard = [
        [InlineKeyboardButton("💰 Earn Coins", callback_data="earn")],
        [InlineKeyboardButton("🏦 Balance", callback_data="balance")],
    ]

    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"💰 Coins: {coins:.2f}\n\n"
        "Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    add_coins(query.from_user.id, COINS_PER_TASK)
    coins = get_user(query.from_user.id)

    await query.edit_message_text(
        f"✅ Task completed!\n\n"
        f"➕ You earned {COINS_PER_TASK} coins\n"
        f"💰 Total: {coins:.2f}"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    coins = get_user(query.from_user.id)

    await query.edit_message_text(
        f"🏦 Your balance:\n\n"
        f"💰 {coins:.2f} coins"
    )


async def menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "earn":
        await earn(update, context)

    elif query.data == "balance":
        await balance(update, context)


# ================== MAIN ==================

def main():
    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(menu_click))

    threading.Thread(
        target=lambda: app_web.run(host="0.0.0.0", port=8080),
        daemon=True,
    ).start()

    print("🤖 Bot is online")
    telegram_app.run_polling()


if __name__ == "__main__":
    main()
