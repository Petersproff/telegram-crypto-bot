import os
import requests
import uuid
import hmac
import hashlib
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request, abort


ORDERS = {}  # order_id -> telegram_user_id
telegram_app = None


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
        "pay_currency": "btc",
        "order_id": str(uuid.uuid4()),
        "order_description": description
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()



from flask import Flask, request, abort

app_web = Flask(__name__)

NOWPAY_IPN_SECRET = os.getenv("NOWPAY_IPN_SECRET")

@app_web.route("/ipn", methods=["POST"])



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

    # ✅ AUTO DELIVERY HERE
    if data.get("payment_status") == "finished":
        order_id = data.get("order_id")
        user_id = ORDERS.get(order_id)

        if user_id and telegram_app:
            telegram_app.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ Payment received!\n\n"
                    "📘 Here is your ebook:\n"
                    "https://your-download-link.com"
                )
            )

    return "OK", 200







async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot is live!\nUse /shop to buy."
    )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    invoice = create_invoice(10, "Ebook Purchase")
    pay_url = invoice.get("invoice_url")
    order_id = invoice.get("order_id")

    if not pay_url or not order_id:
        await update.message.reply_text(
            "❌ Payment system error. Please try again later."
        )
        return

    # Save order -> user mapping
    ORDERS[order_id] = update.effective_user.id

    await update.message.reply_text(
        f"💳 Pay with crypto:\n{pay_url}\n\n"
        "✅ You will receive your product automatically after payment."
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("shop", shop))

    threading.Thread(
        target=lambda: app_web.run(host="0.0.0.0", port=8080),
        daemon=True
    ).start()

    telegram_app.run_polling()
    if __name__ == "__main__":
    main()

