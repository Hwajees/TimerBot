from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from flask import Flask, request
import os
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()
bot = Bot(token=BOT_TOKEN)

session = {
    "active": False,
    "admin_id": None,
    "title": None,
    "speaker1": None,
    "speaker2": None,
    "time_per_turn": None,
    "current_speaker": None,
    "timer_running": False
}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # تفاعل فقط مع المشرف الأول أثناء التسجيل
    if session["active"] and session["admin_id"] != user_id:
        await update.message.reply_text("الجلسة قيد الإدارة. فقط المشرف المسؤول يمكنه تعديل البيانات.")
        return

    # تسجيل البيانات خطوة خطوة
    if not session["active"]:
        session["active"] = True
        session["admin_id"] = user_id
        await update.message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    if session["title"] is None:
        session["title"] = text
        await update.message.reply_text(f"تم تسجيل العنوان: {text}\nأرسل اسم المحاور الأول:")
        return

    if session["speaker1"] is None:
        session["speaker1"] = text
        await update.message.reply_text(f"تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:")
        return

    if session["speaker2"] is None:
        session["speaker2"] = text
        await update.message.reply_text(f"تم تسجيل المحاور الثاني: {text}\nأدخل الوقت لكل مداخلة (مثال: 3د):")
        return

    if session["time_per_turn"] is None:
        session["time_per_turn"] = text
        await update.message.reply_text(f"تم تحديد الوقت: {text}\nاكتب 'ابدأ الوقت' للبدء.")
        return

    # بدء المناظرة
    if text == "ابدأ الوقت":
        session["current_speaker"] = session["speaker1"]
        session["timer_running"] = True
        await update.message.reply_text(f"⏳ تم بدء المناظرة!\nالمتحدث الآن: {session['current_speaker']}")
        return

application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

# Webhook Flask
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok"

# تشغيل Flask مع await للبوت
async def main():
    await bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    asyncio.run(main())
