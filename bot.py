import os
import requests
import uuid
import hmac
import hashlib
import sqlite3
import threading

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request, abort

# ===================== CONFIG =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOWPAY_API_KEY = os.getenv("NOWPAY_API_KEY")
NOWPAY_IPN_SECRET = os.getenv("NOWPAY_IPN_SECRET")

# ===================== DATABASE =====================

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
    conn.commit()
    return conn

db = init_db()

# ===================== PRODUCTS =====================

PRODUCTS = {
    "ebook": {"price": 10, "download": "https://your-download-link.com/ebook.pdf"},
    "course": {"price": 50, "download": "https://your-download-link.com/course.zip"},
    "video": {"price": 25, "download": "https://your-download-link.com/video.mp4"}
}


# ===================== TELEGRAM APP =====================

telegram_app = None

# ===================== NOWPAYMENTS =====================

def create_invoice(amount, description):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "price_amount": amount,
        "price_currency": "usd",
        "pay_currency": "btc",
        "order_id": str(uuid.uuid4()),
        "order_description": description
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# ===================== FLASK IPN =====================

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
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        abort(403)

    data = request.json

    if data and data.get("payment_status") == "finished":
        order_id = data.get("order_id")

        row = db.execute(
            "SELECT user_id FROM orders WHERE order_id=?",
            (order_id,)
        ).fetchone()

        if row:
            user_id = row[0]

            telegram_app.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ Payment received!\n\n"
                    "📘 Your ebook download:\n"
                    "https://your-download-link.com"
                )
            )

            db.execute(
                "UPDATE orders SET status='delivered' WHERE order_id=?",
                (order_id,)
            )
            db.commit()

    return "OK", 200

# ===================== BOT COMMANDS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot is live!\nUse /shop to buy."
    )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 Available products:\n\n"
        "📘 Ebook — $10\n\n"
        "Use /buy ebook"
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /buy ebook")
        return

    product = context.args[0]

    if product not in PRODUCTS:
        await update.message.reply_text("❌ Invalid product")
        return

    price = PRODUCTS[product]["price"]
    invoice = create_invoice(price, product)

    pay_url = invoice.get("invoice_url")
    order_id = invoice.get("order_id")

    if not pay_url or not order_id:
        await update.message.reply_text(
            "❌ Payment system error. Please try again later."
        )
        return

    db.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?)",
        (order_id, update.effective_user.id, product, "pending")
    )
    db.commit()

    await update.message.reply_text(
        f"💳 Pay with crypto:\n{pay_url}\n\n"
        "✅ You will receive your product automatically after payment."
    )

# ===================== MAIN =====================

def main():
    global telegram_app

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("shop", shop))
    telegram_app.add_handler(CommandHandler("buy", buy))

    # Start Flask IPN server in background
    threading.Thread(
        target=lambda: app_web.run(host="0.0.0.0", port=8080),
        daemon=True
    ).start()

    print("🤖 Bot started and polling...")
    telegram_app.run_polling()

if __name__ == "__main__":
    main()
