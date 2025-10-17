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

# نقطة استقبال Webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    # تشغيل معالجة التحديث داخل loop الحالي
    asyncio.create_task(application.process_update(update))
    return "ok", 200

# صفحة فحص
@app.route("/")
def index():
    return "بوت المؤقت يعمل ✅", 200

async def main():
    # تهيئة التطبيق
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook مضبوط بنجاح على {WEBHOOK_URL}")
    # تشغيل التطبيق في الخلفية ليبقى جاهز لمعالجة التحديثات
    await application.start()
    # لا ننهي التطبيق نهائيًا، نتركه مستمرًا
    await asyncio.Event().wait()

if __name__ == "__main__":
    # تشغيل main في thread منفصل قبل Flask
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
