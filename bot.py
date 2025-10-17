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

# إنشاء loop عالمي
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# استقبال Webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    # معالجة التحديث ضمن الـ loop
    asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    return "ok", 200

# صفحة اختبار
@app.route("/", methods=["GET"])
def index():
    return "بوت المؤقت يعمل ✅", 200

async def main():
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook مضبوط بنجاح على {WEBHOOK_URL}")
    await application.start()
    await asyncio.Event().wait()  # إبقاء التطبيق يعمل

if __name__ == "__main__":
    # تشغيل البوت في الخلفية
    loop.create_task(main())
    # تشغيل Flask server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
