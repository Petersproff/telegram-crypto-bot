import os
import uuid
import hmac
import hashlib
import sqlite3
import threading
import requests

from flask import Flask, request, abort
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            product TEXT,
            status TEXT
        )
    """)
    conn.commit()
    return conn

db = init_db()

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
        "price_currency": "usd",
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
                    "✅ Payment confirmed!\n\n"
                    f"🎁 Your download:\n{download}"
                ),
            )

            db.execute(
                "UPDATE orders SET status='delivered' WHERE order_id=?",
                (order_id,),
            )
            db.commit()

    return "OK", 200

# =========================
# TELEGRAM UI
# =========================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛒 Shop", callback_data="shop"),
            InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
        ],
        [
            InlineKeyboardButton("🏦 Bank", callback_data="bank"),
            InlineKeyboardButton("⛏ Earn", callback_data="earn"),
        ],
    ])

def shop_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📘 Ebook – $10", callback_data="buy_ebook"),
        ],
        [
            InlineKeyboardButton("🎓 Course – $25", callback_data="buy_course"),
        ],
        [
            InlineKeyboardButton("⬅ Back", callback_data="back"),
        ],
    ])

# =========================
# HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *CORNIO ARENA*\n\n"
        "🏆 Rating: 1307\n"
        "💰 Balance: $0.00\n\n"
        "🔥 Choose your move:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )

async def menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "shop":
        await query.edit_message_text(
            "🛒 *Shop*\nSelect a product:",
            reply_markup=shop_menu(),
            parse_mode="Markdown",
        )

    elif query.data == "back":
        await query.edit_message_text(
            "🎮 Main Menu",
            reply_markup=main_menu(),
        )

    elif query.data.startswith("buy_"):
        product_key = query.data.replace("buy_", "")
        product = PRODUCTS[product_key]

        invoice = create_invoice(product["price"], product["name"])
        pay_url = invoice.get("invoice_url")
        order_id = invoice.get("order_id")

        if not pay_url:
            await query.edit_message_text("❌ Payment error. Try later.")
            return

        db.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            (order_id, query.from_user.id, product_key, "pending"),
        )
        db.commit()

        await query.edit_message_text(
            f"💳 *Pay Now*\n\n"
            f"{product['name']} – ${product['price']}\n\n"
            f"👉 {pay_url}\n\n"
            "⏳ Delivery is automatic.",
            parse_mode="Markdown",
        )

    else:
        await query.edit_message_text("🚧 Coming soon!")

# =========================
# MAIN
# =========================

def main():
    global telegram_app

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(menu_click))

    threading.Thread(
        target=lambda: app_web.run(host="0.0.0.0", port=8080),
        daemon=True,
    ).start()

    print("🤖 Bot is live")
    telegram_app.run_polling()

if __name__ == "__main__":
    main()
