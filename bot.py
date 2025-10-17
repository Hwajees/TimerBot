import os
import re
import time
import threading
from datetime import timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =============================
# إعداد المتغيرات من البيئة
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
PORT = int(os.getenv("PORT", 10000))

# =============================
# Flask للحفاظ على البوت حي
# =============================
app = Flask(__name__)

@app.route("/")
def home():
    return "بوت المؤقت يعمل ✅"

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

def arabic_to_english(s):
    arabic_numbers = "٠١٢٣٤٥٦٧٨٩"
    english_numbers = "0123456789"
    return "".join(english_numbers[arabic_numbers.index(ch)] if ch in arabic_numbers else ch for ch in s)

async def send_debate_status(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n"
        f"👤 المتحدث الآن: {data['current_speaker']}\n"
        f"⏱️ الوقت المتبقي: {format_time(data['remaining'])}\n"
        f"⏳ الجولة: {data['round']}\n"
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
                          f"({data['duration']}ث)\n🔁 الدور ينتقل الآن إلى: {next_speaker}")
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

    # استدعاء البوت
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

    # إدخال بيانات المناظرة
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
        t = arabic_to_english(text)
        match = re.match(r"(\d+)\s*د", t)
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

    # تعديل البيانات قبل بدء الوقت
    if text.startswith("تعديل "):
        try:
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                await update.message.reply_text("❌ استخدم الصيغة: تعديل عنوان/محاور1/محاور2/وقت <النص>")
                return
            field, new_value = parts[1], parts[2]
            new_value = arabic_to_english(new_value)
            if field in ["عنوان"]:
                data["title"] = new_value
                await update.message.reply_text(f"✅ تم تعديل عنوان المناظرة: {new_value}")
            elif field in ["محاور1", "محاور١"]:
                data["speaker1"] = new_value
                await update.message.reply_text(f"✅ تم تعديل اسم المحاور الأول: {new_value}")
            elif field in ["محاور2", "محاور٢"]:
                data["speaker2"] = new_value
                await update.message.reply_text(f"✅ تم تعديل اسم المحاور الثاني: {new_value}")
            elif field == "وقت":
                match = re.match(r"(\d+)\s*د", new_value)
                if not match:
                    await update.message.reply_text("❌ الرجاء إدخال الوقت بصيغة صحيحة مثل: 5د")
                    return
                minutes = int(match.group(1))
                data["duration"] = minutes * 60
                data["remaining"] = data["duration"]
                await update.message.reply_text(f"✅ تم تعديل الوقت لكل مداخلة: {minutes}د")
            else:
                await update.message.reply_text("❌ لم أفهم ما تريد تعديله. استخدم: عنوان / محاور1 / محاور2 / وقت")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ أثناء التعديل: {e}")
        return

    # بدء الوقت
    if text == "ابدأ الوقت" and data["step"] in ["ready", "running"]:
        data["running"] = True
        data["step"] = "running"
        await update.message.reply_text("⏳ تم بدء المناظرة!")
        thread = threading.Thread(target=timer_thread, args=(context, chat_id))
        thread.start()
        timers[chat_id] = thread
        return

    # أوامر بعد بدء المناظرة
    if data["step"] == "running":
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

    # أمر حالة المناظرة
    if text == "حالة":
        if chat_id not in debate_data:
            await update.message.reply_text("❌ لا توجد مناظرة نشطة.")
            return
        await send_debate_status(context, chat_id)

# =============================
# تشغيل البوت
# =============================
if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Flask للحفاظ على التشغيل
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
    application.run_polling()
