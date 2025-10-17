import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = f"https://timerbot-fjtl.onrender.com/{TOKEN}"

app = Flask(__name__)

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! أنا بوت المؤقت ⏳")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل /start لبدء الاستخدام.")

# إنشاء التطبيق
application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))

# استقبال التحديثات من Telegram
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "ok", 200

# صفحة فحص
@app.route("/")
def index():
    return "بوت المؤقت يعمل ✅", 200

async def setup_webhook():
    print("🚀 بدء تشغيل البوت...")
    await application.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook مضبوط بنجاح على {WEBHOOK_URL}")

if __name__ == "__main__":
    asyncio.run(setup_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
