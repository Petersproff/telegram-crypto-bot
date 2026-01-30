import logging
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
import sqlite3
import threading

# ================= CONFIG =================
BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 749028646
DB_NAME = "gamemode.db"

# ================= LOGGING =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ================= DATABASE =================
def db():
    return sqlite3.connect(DB_NAME)

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price INTEGER,
        active INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        link TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        time TEXT
    )
    """)

    con.commit()
    con.close()

init_db()

# ================= FLASK IPN =================
app_web = Flask(__name__)

@app_web.route("/ipn", methods=["POST"])
def ipn():
    data = request.json
    return jsonify({"ok": True})

def run_flask():
    app_web.run(host="0.0.0.0", port=8080)

# ================= UTIL =================
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ================= ANIMATION =================
async def animated_text(msg, text):
    build = ""
    for c in text:
        build += c
        await msg.edit_text(build)
        await asyncio.sleep(0.03)

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎮")
    await animated_text(msg, "🎮 Welcome to GAMEMODE!\n\n🔥 Play. Earn. Win.\n\nType /shop to begin.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/shop – View store\n"
        "/buy <id> – Buy product\n"
        "/help – Help menu"
    )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, name, price FROM products WHERE active=1")
    rows = cur.fetchall()
    con.close()

    if not rows:
        await update.message.reply_text("🛒 Shop is empty.")
        return

    text = "🛒 *GAMEMODE SHOP*\n\n"
    for r in rows:
        text += f"🆔 {r[0]} | {r[1]} — 💰 {r[2]}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /buy <product_id>")
        return

    pid = context.args[0]

    con = db()
    cur = con.cursor()

    cur.execute("SELECT id FROM products WHERE id=? AND active=1", (pid,))
    product = cur.fetchone()

    if not product:
        await update.message.reply_text("❌ Product not found.")
        con.close()
        return

    cur.execute("SELECT link FROM downloads WHERE product_id=?", (pid,))
    links = cur.fetchall()

    if not links:
        await update.message.reply_text("⚠️ No download links yet.")
        con.close()
        return

    cur.execute(
        "INSERT INTO orders (user_id, product_id, time) VALUES (?, ?, ?)",
        (update.effective_user.id, pid, datetime.utcnow().isoformat())
    )

    con.commit()
    con.close()

    reply = "✅ *Purchase Successful!*\n\n📦 Your Downloads:\n"
    for l in links:
        reply += f"🔗 {l[0]}\n"

    await update.message.reply_text(reply, parse_mode="Markdown")

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "🔐 *ADMIN PANEL*\n\n"
        "/addproduct <name>|<price>\n"
        "/addlink <product_id>|<url>\n"
        "/products",
        parse_mode="Markdown"
    )

async def addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    data = " ".join(context.args)
    if "|" not in data:
        await update.message.reply_text("Format: /addproduct Name|Price")
        return

    name, price = data.split("|")
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
    con.commit()
    con.close()

    await update.message.reply_text("✅ Product added.")

async def addlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    data = " ".join(context.args)
    if "|" not in data:
        await update.message.reply_text("Format: /addlink ProductID|URL")
        return

    pid, url = data.split("|")
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO downloads (product_id, link) VALUES (?, ?)", (pid, url))
    con.commit()
    con.close()

    await update.message.reply_text("🔗 Link added.")

async def products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, name, price FROM products")
    rows = cur.fetchall()
    con.close()

    text = "📦 *ALL PRODUCTS*\n\n"
    for r in rows:
        text += f"{r[0]} | {r[1]} — {r[2]}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("buy", buy))

    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addproduct", addproduct))
    app.add_handler(CommandHandler("addlink", addlink))
    app.add_handler(CommandHandler("products", products))

    threading.Thread(target=run_flask, daemon=True).start()

    print("🤖 Bot is live")
    app.run_polling()

if __name__ == "__main__":
    main()
