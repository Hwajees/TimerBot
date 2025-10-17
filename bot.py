import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = f"https://timerbot-fjtl.onrender.com/{TOKEN}"

app = Flask(__name__)

# ✅ أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! أنا بوت المؤقت ⏳")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل /start لبدء الاستخدام.")

# ✅ إنشاء تطبيق البوت
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))

# ✅ تعيين Webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

# ✅ نقطة البداية (Render سيبدأ من هنا)
@app.route("/")
def index():
    return "بوت المؤقت يعمل ✅", 200

if __name__ == "__main__":
    import asyncio

    async def run():
        print("🚀 بدء تشغيل البوت...")
        await application.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook مضبوط بنجاح على {WEBHOOK_URL}")

    asyncio.run(run())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
