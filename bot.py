import os
import re
import time
import threading
from datetime import timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# =============================
# إعداد المتغيرات من البيئة
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", 0))  # ضع 0 إذا لم يكن هناك ID محدد

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

# تحويل الأرقام العربية إلى إنجليزية
def convert_arabic_numbers(text):
    arabic_to_english = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return text.translate(arabic_to_english)

async def send_debate_status(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    speaker = data["current_speaker"]
    total = data["round"]
    remain = max(0, data["remaining"])
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n"
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
    last_alert = -1
    extra_time = 0
    while True:
        time.sleep(1)
        with lock:
            if chat_id not in debate_data:
                break
            data = debate_data[chat_id]
            if not data["running"]:
                continue
            data["remaining"] -= 1

            # تنبيه قبل انتهاء الوقت (آخر 30 ثانية، كل 10 ثواني)
            if 0 < data["remaining"] <= 30 and data["remaining"] % 10 == 0 and data["remaining"] != last_alert:
                last_alert = data["remaining"]
                context.application.create_task(context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ انتبه! {data['current_speaker']} تبقى {format_time(data['remaining'])} على انتهاء المداخلة!"
                ))

            # انتهاء الوقت
            if data["remaining"] <= 0:
                data["running"] = False
                context.application.create_task(context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 انتهى وقت {data['current_speaker']}!\n⏱️ بدأ حساب الوقت الزائد..."
                ))

                # حساب الوقت الزائد كل 10 ثواني حتى يتم التبديل
                extra_time = 0
                while not data["running"] and chat_id in debate_data:
                    time.sleep(10)
                    extra_time += 10
                    context.application.create_task(context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⌛ الوقت الزائد للمتحدث الحالي {data['current_speaker']}: {format_time(extra_time)}"
                    ))
                break

# =============================
# معالجة الرسائل
# =============================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.effective_user is None:
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    # التحقق من صلاحيات المشرفين
    chat_admins = await context.bot.get_chat_administrators(chat_id)
    if not is_admin(user.id, chat_admins):
        return

    # إنشاء مناظرة جديدة
    if any(word in text for word in ["بوت المؤقت", "المؤقت", "بوت الساعة", "بوت الساعه", "الساعة", "الساعه"]):
        debate_data[chat_id] = {
            "admin": user.id,
            "step": "batch_input",
            "title": "",
            "speaker1": "",
            "speaker2": "",
            "duration": 0,
            "remaining": 0,
            "running": False,
            "current_speaker": "",
            "round": 1
        }
        await update.message.reply_text(
            "تم استدعاء البوت! أرسل بيانات المناظرة بالترتيب مفصولة بسطر لكل واحد:\n"
            "1. عنوان المناظرة\n2. المحاور الأول\n3. المحاور الثاني\n4. الوقت (مثال: 5د)"
        )
        return

    if chat_id not in debate_data:
        return

    data = debate_data[chat_id]

    # ==================== إدخال البيانات دفعة واحدة ====================
    if data["step"] == "batch_input":
        lines = text.split('\n')
        if len(lines) < 4:
            await update.message.reply_text("❌ الرجاء إدخال جميع البيانات الأربعة كل واحد بسطر.")
            return
        data["title"] = lines[0].strip()
        data["speaker1"] = lines[1].strip()
        data["speaker2"] = lines[2].strip()
        dur_text = convert_arabic_numbers(lines[3].strip())
        match = re.match(r"(\d+)\s*د", dur_text)
        if not match:
            await update.message.reply_text("❌ الرجاء إدخال الوقت بصيغة صحيحة مثل: 5د")
            return
        minutes = int(match.group(1))
        data["duration"] = minutes * 60
        data["remaining"] = data["duration"]
        data["current_speaker"] = data["speaker1"]
        data["step"] = "ready"

        await update.message.reply_text(
            f"✅ تم تسجيل البيانات:\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎙️ مناظرة: {data['title']}\n"
            f"👤 المحاورون: 🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            "يمكنك تعديل أي عنصر باستخدام: 'تعديل عنوان/محاور1/محاور2/وقت القيمة الجديدة'\n"
            "اكتب 'ابدأ الوقت' للبدء."
        )
        return

    text_conv = convert_arabic_numbers(text)

    # ==================== تعديل البيانات قبل البدء ====================
    if data["step"] in ["ready", "running"]:
        if text.startswith("تعديل"):
            parts = text.split()
            if len(parts) >= 3:
                field = parts[1].lower()
                value = " ".join(parts[2:])
                value = convert_arabic_numbers(value)
                if field in ["عنوان", "title"]:
                    data["title"] = value
                    await update.message.reply_text(f"✅ تم تعديل عنوان المناظرة: {value}")
                    return
                if field in ["محاور1", "محاور١", "speaker1"]:
                    data["speaker1"] = value
                    await update.message.reply_text(f"✅ تم تعديل اسم المحاور الأول: {value}")
                    return
                if field in ["محاور2", "محاور٢", "speaker2"]:
                    data["speaker2"] = value
                    await update.message.reply_text(f"✅ تم تعديل اسم المحاور الثاني: {value}")
                    return
                if field in ["وقت", "time"]:
                    match = re.search(r"\d+", value)
                    if match:
                        minutes = int(match.group(0))
                        data["duration"] = minutes * 60
                        data["remaining"] = data["duration"]
                        await update.message.reply_text(f"✅ تم تعديل الوقت لكل مداخلة: {minutes}د")
                        return
            await update.message.reply_text("❌ لم أفهم ما تريد تعديله. استخدم: عنوان / محاور1 / محاور2 / وقت")
            return

    # ==================== بدء الوقت ====================
    if text == "ابدأ الوقت" and data["step"] == "ready":
        data["running"] = True
        data["step"] = "running"
        await update.message.reply_text(f"⏳ تم بدء المناظرة! المتحدث الآن: {data['current_speaker']}")
        thread = threading.Thread(target=timer_thread, args=(context, chat_id))
        thread.start()
        timers[chat_id] = thread
        return

    # ==================== أوامر أثناء التشغيل ====================
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
        if text == "حالة المناظرة":
            await send_debate_status(context, chat_id)
            return
        if text == "نهاية":
            await update.message.reply_text("📊 تم إنهاء المناظرة.")
            debate_data.pop(chat_id, None)
            return

        # ===== أوامر التحكم بالوقت بعد البداية =====
        if text_conv == "تنازل":
            next_speaker = data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
            await context.bot.send_message(chat_id=chat_id, text=f"🚨 تنازل {data['current_speaker']} عن المداخلة!\n🔁 الدور ينتقل الآن إلى: {next_speaker}")
            data["current_speaker"] = next_speaker
            data["remaining"] = data["duration"]
            data["round"] += 1
            return

        add_match = re.match(r"اضف\s*(\d+)([دث])", text_conv)
        if add_match:
            amount = int(add_match.group(1))
            unit = add_match.group(2)
            if unit == "د":
                amount *= 60
            data["remaining"] += amount
            await update.message.reply_text(f"✅ تم إضافة {amount//60 if unit=='د' else amount}{unit} للمتحدث الحالي")
            return

        sub_match = re.match(r"انقص\s*(\d+)([دث])", text_conv)
        if sub_match:
            amount = int(sub_match.group(1))
            unit = sub_match.group(2)
            if unit == "د":
                amount *= 60
            data["remaining"] = max(0, data["remaining"] - amount)
            await update.message.reply_text(f"✅ تم إنقاص {amount//60 if unit=='د' else amount}{unit} من المتحدث الحالي")
            return

        if text_conv == "اعادة":
            data["remaining"] = data["duration"]
            await update.message.reply_text(f"♻️ تم إعادة وقت المداخلة للمتحدث الحالي إلى {data['duration']//60}د")
            return

# =============================
# تشغيل البوت
# =============================
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

if __name__ == "__main__":
    application.run_polling()
