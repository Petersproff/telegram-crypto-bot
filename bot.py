import os
import uuid
import hmac
import hashlib
import sqlite3
import threading
import asyncio
import requests

from flask import Flask, request, abort
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
 
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOWPAY_API_KEY = os.getenv("NOWPAY_API_KEY")
NOWPAY_IPN_SECRET = os.getenv("NOWPAY_IPN_SECRET")

telegram_app = None

# =========================
# PRODUCTS
# =========================

PRODUCTS = {
    "ebook": {
        "name": "📘 Crypto Ebook",
        "price": 10,
        "download": "https://your-download-link.com/ebook.pdf",
    },
    "course": {
        "name": "🎓 Trading Course",
        "price": 25,
        "download": "https://your-download-link.com/course",
    },
}

# =========================
# DATABASE
# =========================
def init_db():
    conn = sqlite3.connect("orders.db", check_same_thread=False)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            product TEXT,
            status TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS coins (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    return conn



async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🪙 *EARN COINS MODE*\n\n"
        "⚡ Task: Visit Gamemode Hub\n"
        "🎁 Reward: +7 Coins\n\n"
        "🌐 Open link below, complete the task,\n"
        "then return and use /claim",
        parse_mode="Markdown"
    )

    await update.message.reply_text(
        "👉 https://your-vercel-link.vercel.app"
    )
async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    row = db.execute(
        "SELECT balance FROM coins WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if row is None:
        db.execute(
            "INSERT INTO coins (user_id, balance) VALUES (?, ?)",
            (user_id, 7)
        )
        balance = 7
    else:
        balance = row[0] + 7
        db.execute(
            "UPDATE coins SET balance=? WHERE user_id=?",
            (balance, user_id)
        )

    db.commit()

    await update.message.reply_text(
        "🎉 *TASK COMPLETED!*\n\n"
        "🪙 You earned +7 coins\n"
        f"💰 Balance: {balance} coins",
        parse_mode="Markdown"
    )


# =========================
# NOWPAYMENTS
# =========================

def create_invoice(amount, description):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "price_amount": amount,
        "price_currency"def init_db():
    conn = sqlite3.connect("orders.db", check_same_thread=False)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            product TEXT,
            status TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS coins (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    return conn
: "usd",
        "pay_currency": "btc",
        "order_id": str(uuid.uuid4()),
        "order_description": description,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    return r.json()

# =========================
# FLASK IPN
# =========================

app_web = Flask(__name__)

@app_web.route("/ipn", methods=["POST"])
def ipn():
    received_sig = request.headers.get("x-nowpayments-sig")
    payload = request.data

    if not received_sig:
        abort(400)

    expected_sig = hmac.new(
        NOWPAY_IPN_SECRET.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        abort(403)

    data = request.json

    if data and data.get("payment_status") == "finished":
        order_id = data.get("order_id")

        row = db.execute(
            "SELECT user_id, product FROM orders WHERE order_id=?",
            (order_id,),
        ).fetchone()

        if row:
            user_id, product = row
            download = PRODUCTS[product]["download"]

            telegram_app.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ *Payment Confirmed!*\n\n"
                    "🎁 Your reward is ready:\n"
                    f"{download}"
                ),
                parse_mode="Markdown",
            )

            db.execute(
                "UPDATE orders SET status='delivered' WHERE order_id=?",
                (order_id,),
            )
            db.commit()

    return "OK", 200

# =========================
# UI MENUS
# =========================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛒 Shop", callback_data="shop"),
            InlineKeyboardButton("⛏ Earn", callback_data="earn"),
        ],
        [
            InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
            InlineKeyboardButton("🏦 Bank", callback_data="bank"),
        ],
    ])
def shop_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📘 Ebook — $10", callback_data="buy_ebook")],
        [InlineKeyboardButton("🎓 Course — $25", callback_data="buy_course")],
        [InlineKeyboardButton("⬅ Back", callback_data="back")],
    ])

# =========================
# ANIMATED START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    await chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1.2)
    await update.message.reply_text("🔌 Connecting to *Gamemode*...", parse_mode="Markdown")

    await chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1.2)
    await update.message.reply_text("🔐 Syncing wallet & stats...")

    await chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1.2)
    await update.message.reply_text(
        "🎮 *WELCOME TO GAMEMODE*\n\n"
        "🏆 Rank: Challenger\n"
        "💰 Balance: $0.00\n"
        "📦 Inventory: Empty\n\n"
        "🔥 Choose your next move:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )

# =========================
# MENU HANDLER
# =========================

async def menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "shop":
        await query.edit_message_text(
            "🛒 *Gamemode Shop*\nSelect an item:",
            reply_markup=shop_menu(),
            parse_mode="Markdown",
        )

    elif query.data == "back":
        await query.edit_message_text(
            "🎮 *Gamemode Dashboard*",
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )

    elif query.data.startswith("buy_"):
        product_key = query.data.replace("buy_", "")
        product = PRODUCTS[product_key]

        await query.edit_message_text("⏳ Creating secure invoice...")
        await asyncio.sleep(1.2)

        invoice = create_invoice(product["price"], product["name"])
        pay_url = invoice.get("invoice_url")
        order_id = invoice.get("order_id")

        if not pay_url:
            await query.edit_message_text("❌ Payment system unavailable. Try later.")
            return

        db.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            (order_id, query.from_user.id, product_key, "pending"),
        )
        db.commit()

        await query.edit_message_text(
            f"💳 *Payment Ready*\n\n"
            f"{product['name']} — ${product['price']}\n\n"
            f"👉 {pay_url}\n\n"
            "⚡ Auto-delivery enabled",
            parse_mode="Markdown",
        )

    else:
        await query.edit_message_text("🚧 Feature unlocking soon...")

# =========================
# MAIN
# =========================

def main():
    global telegram_app

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(menu_click))
telegram_app.add_handler(CommandHandler("earn", earn))
telegram_app.add_handler(CommandHandler("claim", claim))
 

    threading.Thread(
        target=lambda: app_web.run(host="0.0.0.0", port=8080),
        daemon=True,
    ).start()

    print("🎮 Gamemode bot online")
    telegram_app.run_polling()

if __name__ == "__main__":
    main()
