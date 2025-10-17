import os
import re
import asyncio
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
# مؤقت المناظرة
# =============================
async def timer_task(context: ContextTypes.DEFAULT_TYPE, chat_id):
    last_alert = -1
    data = debate_data.get(chat_id)
    if not data:
        return

    while chat_id in debate_data and data["running"]:
        await asyncio.sleep(1)
        data["remaining"] -= 1

        # تنبيه قبل انتهاء الوقت (آخر 30 ثانية، كل 10 ثواني)
        if 0 < data["remaining"] <= 30 and data["remaining"] % 10 == 0 and data["remaining"] != last_alert:
            last_alert = data["remaining"]
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏳ انتبه! {data['current_speaker']} تبقى {format_time(data['remaining'])} على انتهاء المداخلة!"
            )

        # انتهاء الوقت
        if data["remaining"] <= 0:
            data["running"] = False
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚨 انتهى وقت {data['current_speaker']}!\n⏱️ بدأ حساب الوقت الزائد..."
            )

            # حساب الوقت الزائد كل 10 ثواني حتى تبديل الدور
            extra = 0
            while not data["running"] and chat_id in debate_data:
                await asyncio.sleep(10)
                extra += 10
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⌛ الوقت الزائد للمتحدث الحالي {data['current_speaker']}: {format_time(extra)}"
                )

# =============================
# معالجة الرسائل
# =============================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    chat_admins = await context.bot.get_chat_administrators(chat_id)
    if not is_admin(user.id, chat_admins):
        return

    # ==================== بدء مناظرة جديدة ====================
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
            "تم استدعاء البوت! أرسل بيانات المناظرة بالترتيب، كل عنصر في سطر جديد:\n"
            "1️⃣ عنوان المناظرة\n2️⃣ المحاور الأول\n3️⃣ المحاور الثاني\n4️⃣ الوقت (مثال: 5د)"
        )
        return

    if chat_id not in debate_data:
        return

    data = debate_data[chat_id]

    # ==================== إدخال البيانات دفعة واحدة ====================
    if data["step"] == "batch_input":
        lines = text.split('\n')
        if len(lines) < 4:
            await update.message.reply_text("❌ الرجاء إدخال جميع البيانات الأربعة، كل واحد بسطر.")
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
            f"🎙️ مناظرة: {data['title']}\n"
            f"👤 المحاورون: 🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            "يمكنك تعديل أي عنصر باستخدام: 'تعديل عنوان/محاور1/محاور2/وقت القيمة الجديدة'\n"
            "اكتب 'ابدأ الوقت' للبدء."
        )
        return

    # تحويل الأرقام العربية للإنجليزية
    text_conv = convert_arabic_numbers(text)

    # ==================== تعديل البيانات قبل بدء المناظرة ====================
    if data["step"] == "ready" and text.startswith("تعديل"):
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

    # ==================== بدء المناظرة ====================
    if text == "ابدأ الوقت" and data["step"] == "ready":
        data["running"] = True
        data["step"] = "running"
        await update.message.reply_text("⏳ تم بدء المناظرة!")
        asyncio.create_task(timer_task(context, chat_id))
        return

    # ==================== أوامر أثناء المناظرة ====================
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
            asyncio.create_task(timer_task(context, chat_id))
            await update.message.reply_text("▶️ تم استئناف المؤقت.")
            return

        if text == "تبديل":
            data["current_speaker"] = data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
            data["remaining"] = data["duration"]
            data["round"] += 1
            data["running"] = True
            asyncio.create_task(timer_task(context, chat_id))
            await update.message.reply_text(f"🔁 تم التبديل إلى: {data['current_speaker']}")
            return

        if text == "حالة المناظرة":
            await send_debate_status(context, chat_id)
            return

        if text == "نهاية":
            await update.message.reply_text("📊 تم إنهاء المناظرة.")
            debate_data.pop(chat_id, None)
            return

        # أوامر التحكم بالوقت بعد البداية
        if text_conv == "تنازل":
            next_speaker = data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
            await context.bot.send_message(chat_id=chat_id,
                text=f"🚨 تنازل {data['current_speaker']} عن المداخلة!\n🔁 الدور ينتقل الآن إلى: {next_speaker}")
            data["current_speaker"] = next_speaker
            data["remaining"] = data["duration"]
            data["round"] += 1
            data["running"] = True
            asyncio.create_task(timer_task(context, chat_id))
            return

        add_match = re.match(r"اضف\s*(\d+)([دث])", text_conv)
        if add_match:
            amount = int(add_match.group(1))
            unit = add_match.group(2)
            if unit == "د":
                amount *= 60
            data["remaining"] += amount
            await update.message.reply_text(f"✅ تم إضافة {amount if unit=='ث' else amount//60}{unit} للمتحدث الحالي")
            return

        sub_match = re.match(r"انقص\s*(\d+)([دث])", text_conv)
        if sub_match:
            amount = int(sub_match.group(1))
            unit = sub_match.group(2)
            if unit == "د":
                amount *= 60
            data["remaining"] = max(0, data["remaining"] - amount)
            await update.message.reply_text(f"✅ تم إنقاص {amount if unit=='ث' else amount//60}{unit} من المتحدث الحالي")
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
