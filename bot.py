import os
import requests
import uuid
import hmac
import hashlib
import sqlite3
import threading
import asyncio

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ChatAction
from flask import Flask, request, abort

# ===================== CONFIG =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOWPAY_API_KEY = os.getenv("NOWPAY_API_KEY")
NOWPAY_IPN_SECRET = os.getenv("NOWPAY_IPN_SECRET")
ADMINS = [123456789]  # <-- Replace with your Telegram user ID(s)

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
    "ebook": {
        "price": 10,
        "downloads": [
            "https://your-download-link.com/ebook.pdf",
            "https://your-download-link.com/ebook-supplement.pdf"
        ]
    },
    "course": {
        "price": 50,
        "downloads": [
            "https://your-download-link.com/course.zip"
        ]
    },
    "video": {
        "price": 25,
        "downloads": [
            "https://your-download-link.com/video.mp4",
            "https://your-download-link.com/video-extra.mp4"
        ]
    }
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
            "SELECT user_id, product FROM orders WHERE order_id=?",
            (order_id,)
        ).fetchone()

        if row:
            user_id, product_name = row
            download_links = PRODUCTS[product_name]["downloads"]
            links_text = "\n".join([f"🔗 {link}" for link in download_links])

            telegram_app.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ Payment received!\n\n"
                    f"📘 Your {product_name} downloads:\n"
                    f"{links_text}"
                )
            )

            db.execute(
                "UPDATE orders SET status='delivered' WHERE order_id=?",
                (order_id,)
            )
            db.commit()

    return "OK", 200

# ===================== ADMIN DECORATOR =====================

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMINS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        await func(update, context)
    return wrapper

# ===================== BOT COMMANDS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    await update.message.reply_animation(
        animation="https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
        caption="🤖 *Bot is live!*\nUse /shop to see available products.",
        parse_mode="Markdown"
    )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)

    text = "🛒 *Available Products:*\n\n"
    for name, p in PRODUCTS.items():
        text += f"• *{name.title()}* — 💵 ${p['price']}\n"
    text += "\nUse /buy `<product>` to purchase, e.g., /buy `ebook`"

    await update.message.reply_animation(
        animation="https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
        caption=text,
        parse_mode="Markdown"
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /buy <product>, e.g., /buy ebook")
        return

    product = context.args[0].lower()
    if product not in PRODUCTS:
        await update.message.reply_text("❌ Invalid product. Use /shop to see available products.")
        return

    price = PRODUCTS[product]["price"]
    invoice = create_invoice(price, product)

    pay_url = invoice.get("invoice_url")
    order_id = invoice.get("order_id")

    if not pay_url or not order_id:
        await update.message.reply_text("❌ Payment system error. Please try again later.")
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

# ===================== ADMIN COMMANDS =====================

@admin_only
async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.execute("SELECT order_id, user_id, product, status FROM orders").fetchall()
    if not rows:
        await update.message.reply_text("No orders yet.")
        return

    text = "📋 Orders:\n\n"
    for order_id, user_id, product, status in rows:
        text += f"• {order_id} — User: {user_id} — Product: {product} — Status: {status}\n"
    await update.message.reply_text(text)

@admin_only
async def addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /addproduct name price link1,link2,...")
        return

    name = context.args[0].lower()
    price = float(context.args[1])
    links = " ".join(context.args[2:]).split(",")

    PRODUCTS[name] = {"price": price, "downloads": links}
    await update.message.reply_text(f"✅ Product {name} added with {len(links)} files.")

# ===================== MAIN =====================

def main():
    global telegram_app

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("shop", shop))
    telegram_app.add_handler(CommandHandler("buy", buy))
    telegram_app.add_handler(CommandHandler("orders", orders))
    telegram_app.add_handler(CommandHandler("addproduct", addproduct))

    threading.Thread(
        target=lambda: app_web.run(host="0.0.0.0", port=8080),
        daemon=True
    ).start()

    print("🤖 Bot started and polling...")
    telegram_app.run_polling()

if __name__ == "__main__":
    main()
