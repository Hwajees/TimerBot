from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

app = Flask(__name__)

application = ApplicationBuilder().token(BOT_TOKEN).build()
bot = Bot(token=BOT_TOKEN)

# حالة الجلسة
session = {
    "active": False,
    "admin_id": None,
    "title": None,
    "speaker1": None,
    "speaker2": None,
    "time_per_turn": None,
    "current_speaker": None,
    "timer_running": False,
    "time_left": 0,
    "round": 1,
}

# ========================
# وظائف البوت
# ========================
async def start_debate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    user_id = update.effective_user.id

    # أول مشرف يبدأ الجلسة
    if not session["active"]:
        session["active"] = True
        session["admin_id"] = user_id
        await update.message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return
    # أي مشرف بعد البداية
    if user_id == session["admin_id"]:
        await update.message.reply_text("الجلسة مستمرة، يمكنك التحكم بالأوامر.")
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return  # تجاهل الأعضاء العاديين خارج المجموعة

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # تحقق من المشرف
    if not session["active"] or (user_id != session["admin_id"] and session["admin_id"] is not None):
        await update.message.reply_text("هذه الجلسة قيد الإدارة، يمكنك استخدام الأوامر إذا كنت مشرفًا.")
        return

    # أمثلة: تسجيل بيانات
    if session["title"] is None:
        session["title"] = text
        await update.message.reply_text(f"تم تسجيل العنوان: {text}\nالآن أرسل اسم المحاور الأول:")
        return
    if session["speaker1"] is None:
        session["speaker1"] = text
        await update.message.reply_text(f"تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:")
        return
    if session["speaker2"] is None:
        session["speaker2"] = text
        await update.message.reply_text("الآن أدخل الوقت لكل مداخلة (مثال: 3د):")
        return
    if session["time_per_turn"] is None:
        session["time_per_turn"] = text
        await update.message.reply_text(
            f"تم تحديد الوقت: {text}\nاكتب 'ابدأ الوقت' للبدء."
        )
        return

    # أوامر التحكم
    if text == "ابدأ الوقت":
        await update.message.reply_text(f"⏳ تم بدء المناظرة! المتحدث الآن: {session['speaker1']}")
        session["current_speaker"] = session["speaker1"]
        session["timer_running"] = True
        return

# ========================
# Handlers
# ========================
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), start_debate))

# ========================
# Webhook Flask
# ========================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok"

# ========================
# تشغيل Flask
# ========================
if __name__ == "__main__":
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=PORT)
