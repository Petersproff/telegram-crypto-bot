import os
import requests
import uuid
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOWPAY_API_KEY = os.getenv("NOWPAY_API_KEY")

def create_invoice(amount, description):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "price_amount": amount,
        "price_currency": "usd",
        "pay_currency": "usdt",
        "order_id": str(uuid.uuid4()),
        "order_description": description
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot is live!\nUse /shop to buy."
    )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 Product:\n📘 Ebook – 10 USDT\nCrypto payment coming next."
    )

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shop", shop))
    app.run_polling()

if __name__ == "__main__":
    main()
