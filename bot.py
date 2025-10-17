import os
import re
import time
import threading
from datetime import timedelta
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler,
    filters, ContextTypes
)

# =============================
# إعداد المتغيرات من البيئة
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
PORT = int(os.getenv("PORT", 10000))

# =============================
# تشغيل Flask للحفاظ على عمل البوت
# =============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

# =============================
# المتغيرات العامة
# =============================
debate_data = {}
timers = {}
lock = threading.Lock()

# =============================
# أدوات مساعدة
# =============================
def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))

def is_admin(user_id, admins):
    return any(admin.user.id == user_id for admin in admins)

# =============================
# إرسال حالة المناظرة
# =============================
async def send_debate_status(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    speaker = data["current_speaker"]
    total = data["round"]
    remain = max(0, data["remaining"])
    elapsed = data["duration"] - remain

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n\n"
        f"👤 المتحدث الآن: {speaker}\n"
        f"⏱️ الوقت المتبقي: {format_time(remain)}\n"
        f"⏳ الجولة: {total}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=chat_id, text=text)

# =============================
# التحكم في المؤقت
# =============================
def timer_thread(context: ContextTypes.DEFAULT_TYPE, chat_id):
    while True:
        time.sleep(1)
        with lock:
            if chat_id not in debate_data or not debate_data[chat_id]["running"]:
                break
            data = debate_data[chat_id]
            data["remaining"] -= 1
            if data["remaining"] <= 0:
                data["running"] = False
                next_speaker = data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
                context.application.create_task(context.bot.send_message(
                    chat_id=chat_id,
                    text=(f"🚨 انتهى وقت المحاور!\n👤 {data['current_speaker']} أكمل وقته المحدد "
                          f"({data['duration']//60}د)\n🔁 الدور ينتقل الآن إلى: {next_speaker}")
                ))
                data["current_speaker"] = next_speaker
                data["remaining"] = data["duration"]
                data["round"] += 1
                break

# =============================
# معالجة الرسائل
# =============================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    # التحقق من صلاحيات المشرفين
    chat_admins = await context.bot.get_chat_administrators(chat_id)
    if not is_admin(user.id, chat_admins):
        return  # تجاهل الأعضاء العاديين تمامًا

    # إنشاء مناظرة جديدة
    if any(word in text for word in ["بوت المؤقت", "المؤقت", "بوت الساعة", "بوت الساعه", "الساعة", "الساعه"]):
        debate_data[chat_id] = {
            "admin": user.id,
            "step": "title",
            "title": "",
            "speaker1": "",
            "speaker2": "",
            "duration": 0,
            "remaining": 0,
            "running": False,
            "current_speaker": "",
            "round": 1
        }
        await update.message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    if chat_id not in debate_data:
        return  # لا توجد مناظرة نشطة

    data = debate_data[chat_id]

    # =============================
    # أوامر التعديل قبل بدء الوقت
    # =============================
    if data["step"] == "ready" and text.startswith("تعديل"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("❌ الرجاء كتابة البيانات المراد تعديلها بعد كلمة 'تعديل'")
            return
        edit_text = parts[1]

        if edit_text.startswith("عنوان"):
            data["title"] = edit_text.replace("عنوان", "").strip()
            await update.message.reply_text(f"✅ تم تعديل عنوان المناظرة: {data['title']}")
        elif edit_text.startswith("محاور1"):
            data["speaker1"] = edit_text.replace("محاور1", "").strip()
            await update.message.reply_text(f"✅ تم تعديل اسم المحاور الأول: {data['speaker1']}")
        elif edit_text.startswith("محاور2"):
            data["speaker2"] = edit_text.replace("محاور2", "").strip()
            await update.message.reply_text(f"✅ تم تعديل اسم المحاور الثاني: {data['speaker2']}")
        elif edit_text.startswith("وقت"):
            match = re.match(r"وقت\s*(\d+)\s*د", edit_text)
            if match:
                minutes = int(match.group(1))
                data["duration"] = minutes * 60
                data["remaining"] = data["duration"]
                await update.message.reply_text(f"✅ تم تعديل الوقت لكل مداخلة: {minutes}د")
            else:
                await update.message.reply_text("❌ صيغة الوقت غير صحيحة، مثال: وقت 5د")
        else:
            await update.message.reply_text("❌ لم أفهم ما تريد تعديله. استخدم: عنوان / محاور1 / محاور2 / وقت")
        return

    # =============================
    # خطوات إدخال بيانات المناظرة
    # =============================
    if data["step"] == "title":
        data["title"] = text
        data["step"] = "speaker1"
        await update.message.reply_text(f"✅ تم تسجيل العنوان: {text}\nالآن أرسل اسم المحاور الأول:")
        return

    if data["step"] == "speaker1":
        data["speaker1"] = text
        data["step"] = "speaker2"
        await update.message.reply_text(f"✅ تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:")
        return

    if data["step"] == "speaker2":
        data["speaker2"] = text
        data["step"] = "duration"
        await update.message.reply_text(f"✅ تم تسجيل المحاور الثاني: {text}\nأدخل الوقت لكل مداخلة (مثال: 5د):")
        return

    if data["step"] == "duration":
        match = re.match(r"(\d+)\s*د", text)
        if not match:
            await update.message.reply_text("الرجاء إدخال الوقت بصيغة صحيحة مثل: 5د")
            return
        minutes = int(match.group(1))
        data["duration"] = minutes * 60
        data["remaining"] = data["duration"]
        data["current_speaker"] = data["speaker1"]
        data["step"] = "ready"
        await update.message.reply_text(
            f"🎙️ مناظرة: {data['title']}\n"
            f"👤 المحاورون: 🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            "اكتب 'ابدأ الوقت' للبدء."
        )
        return

    # =============================
    # بدء الوقت
    # =============================
    if text == "ابدأ الوقت" and data["step"] == "ready":
        data["running"] = True
        data["step"] = "running"
        await update.message.reply_text("⏳ تم بدء المناظرة!")
        thread = threading.Thread(target=timer_thread, args=(context, chat_id))
        thread.start()
        timers[chat_id] = thread
        return

    # =============================
    # أوامر التحكم بعد البدء
    # =============================
    if data["step"] == "running":
        if text.startswith("تعديل"):
            await update.message.reply_text("❌ لا يمكن تعديل البيانات بعد بدء العد.")
            return
        if text == "توقف":
            data["running"] = False
            await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت المتبقي: {format_time(data['remaining'])}")
            return
        if text == "استئناف":
            if data["running"]:
                await update.message.reply_text("المؤقت يعمل بالفعل.")
                return
            data["running"] = True
            thread = threading.Thread(target=timer_thread, args=(context, chat_id))
            thread.start()
            timers[chat_id] = thread
            await update.message.reply_text("▶️ تم استئناف المؤقت.")
            return
        if text == "تبديل":
            data["current_speaker"] = data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
            data["remaining"] = data["duration"]
            data["round"] += 1
            await update.message.reply_text(f"🔁 تم التبديل إلى: {data['current_speaker']}")
            return
        if text == "نهاية":
            await update.message.reply_text("📊 تم إنهاء المناظرة.")
            debate_data.pop(chat_id, None)
            return

# =============================
# تشغيل البوت
# =============================
if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Flask للحفاظ على التشغيل
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
    application.run_polling()
