import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# حالة البوت
sessions = {}  # {chat_id: session_data}

# تسجيل المشرفين تلقائياً
def get_or_add_admin(session, user_id):
    if "admins" not in session:
        session["admins"] = []
    if user_id not in session["admins"]:
        session["admins"].append(user_id)
    return session["admins"]

# بدء البوت عند أي رسالة في المجموعة
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if chat_id != GROUP_ID:
        return  # تجاهل أي رسائل خارج المجموعة

    # إنشاء جلسة جديدة إذا لم تكن موجودة
    if chat_id not in sessions:
        sessions[chat_id] = {
            "step": 0,  # خطوات التسجيل
            "data": {},
            "admins": [],
            "turn": 0,  # الدور الحالي
            "time_left": 0
        }

    session = sessions[chat_id]

    # تسجيل أول مشرف
    if session["step"] == 0:
        get_or_add_admin(session, user_id)

    # تحقق من المشرف
    if user_id not in session["admins"]:
        return  # تجاهل الأعضاء العاديين

    # خطوات التسجيل
    if session["step"] == 0 and text.lower() in ["بوت المؤقت", "المؤقت", "بوت الساعة", "بوت الساعه", "الساعة", "الساعه"]:
        await update.message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        session["step"] = 1
        return

    if session["step"] == 1:
        session["data"]["title"] = text
        await update.message.reply_text(f"تم تسجيل العنوان: {text}\nالآن أرسل اسم المحاور الأول:")
        session["step"] = 2
        return

    if session["step"] == 2:
        session["data"]["speaker1"] = text
        await update.message.reply_text(f"تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:")
        session["step"] = 3
        return

    if session["step"] == 3:
        session["data"]["speaker2"] = text
        await update.message.reply_text(f"تم تسجيل المحاور الثاني: {text}\nأدخل الوقت لكل مداخلة (مثال: 3د):")
        session["step"] = 4
        return

    if session["step"] == 4:
        session["data"]["duration"] = text
        await update.message.reply_text(
            f"تم تحديد الوقت: {text}.\nاكتب 'ابدأ الوقت' للبدء."
        )
        session["step"] = 5
        return

    # إدارة الأوامر أثناء الجلسة
    if session["step"] >= 5:
        if text.lower() == "ابدأ الوقت":
            session["turn"] = 1
            await update.message.reply_text(
                f"⏳ تم بدء المناظرة!\nالمتحدث الآن: 🟢 {session['data']['speaker1']}"
            )
        elif text.lower() == "تبديل":
            session["turn"] = 2 if session["turn"] == 1 else 1
            speaker = session["data"]["speaker1"] if session["turn"] == 1 else session["data"]["speaker2"]
            color = "🟢" if session["turn"] == 1 else "🔵"
            await update.message.reply_text(f"🔁 الدور الآن: {color} {speaker}")
        elif text.lower() == "نهاية":
            s1, s2 = session["data"]["speaker1"], session["data"]["speaker2"]
            await update.message.reply_text(
                f"🕒 المناظرة انتهت!\nالمتحدثون: 🟢 {s1} 🔵 {s2}"
            )
        # يمكن إضافة بقية الأوامر هنا بنفس الطريقة

# إنشاء التطبيق وتشغيله
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook
async def on_startup(app):
    await app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

app.post_init = on_startup

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )
