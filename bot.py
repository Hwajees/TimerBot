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
GROUP_ID = int(os.getenv("GROUP_ID", 0))

# =============================
# المتغيرات العامة
# =============================
debate_data = {}
tasks = {}

# =============================
# أدوات مساعدة
# =============================
def format_time(seconds):
    """صيغة الوقت 00:00"""
    m, s = divmod(int(seconds), 60)
    return f"{m:02}:{s:02}"

def convert_arabic_numbers(text):
    return text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

def get_speaker_color(data, speaker):
    return "🟢" if speaker == data["speaker1"] else "🔵"

async def send_debate_status(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    color = get_speaker_color(data, data["current_speaker"])
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n"
        f"👤 المتحدث الآن: {color} {data['current_speaker']}\n"
        f"⏱️ الوقت المتبقي: {format_time(data['remaining'])}\n"
        f"🕐 الوقت الزائد: +{format_time(data.get('extra_time', 0))}\n"
        f"📍 الجولة: {data['round']}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=chat_id, text=text)

# =============================
# المؤقت الرئيسي
# =============================
async def timer_task(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    last_alert = -1

    while chat_id in debate_data and data["running"]:
        await asyncio.sleep(1)

        if data["remaining"] > 0:
            data["remaining"] -= 1
            # تنبيهات العد التنازلي
            if data["remaining"] in [30, 20, 10] and data["remaining"] != last_alert:
                last_alert = data["remaining"]
                color = get_speaker_color(data, data["current_speaker"])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ انتبه! {color} {data['current_speaker']} تبقى {format_time(data['remaining'])} على انتهاء المداخلة!"
                )
        else:
            # بدء الوقت الزائد
            if not data.get("extra_mode", False):
                data["extra_mode"] = True
                data["extra_time"] = 0
                color = get_speaker_color(data, data["current_speaker"])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 انتهى وقت {color} {data['current_speaker']}!\n⏱️ بدأ حساب الوقت الزائد..."
                )

            await asyncio.sleep(1)
            data["extra_time"] += 1

            if data["extra_time"] <= 30:
                if data["extra_time"] % 10 == 0:
                    color = "🔴"
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⌛ الوقت الزائد للمتحدث الحالي {color} {data['current_speaker']}: +{format_time(data['extra_time'])}"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏱️ توقف وقت {data['current_speaker']}!\n🚨 يجب تبديل المحاور..."
                )
                data["running"] = False
                break

# =============================
# معالجة الأوامر
# =============================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not update.message or not update.message.text:
        return
    text = convert_arabic_numbers(update.message.text.strip())

    chat_admins = await context.bot.get_chat_administrators(chat_id)
    if not any(admin.user.id == user.id for admin in chat_admins):
        return

    # استدعاء البوت
    if any(word in text for word in ["بوت المؤقت", "المؤقت", "بوت الساعة", "بوت الساعه", "الساعة", "الساعه"]):
        debate_data[chat_id] = {
            "admin": user.id,
            "step": "setup",
            "title": "",
            "speaker1": "",
            "speaker2": "",
            "duration": 0,
            "remaining": 0,
            "running": False,
            "current_speaker": "",
            "round": 1,
            "extra_time": 0,
            "extra_mode": False,
            "total_extra": {1: 0, 2: 0},
        }
        await update.message.reply_text(
            "تم استدعاء البوت! أرسل البيانات بالترتيب، كل سطر منفصل:\n"
            "1️⃣ عنوان المناظرة\n2️⃣ المحاور الأول\n3️⃣ المحاور الثاني\n4️⃣ الوقت (مثال: 5د)"
        )
        return

    if chat_id not in debate_data:
        return

    data = debate_data[chat_id]

    # إدخال البيانات
    if data["step"] == "setup":
        lines = text.split("\n")
        if len(lines) < 4:
            await update.message.reply_text("❌ الرجاء إدخال جميع البيانات الأربعة كل واحد بسطر.")
            return

        data["title"] = lines[0].strip()
        data["speaker1"] = lines[1].strip()
        data["speaker2"] = lines[2].strip()
        match = re.match(r"(\d+)\s*د", lines[3])
        if not match:
            await update.message.reply_text("❌ الوقت بصيغة غير صحيحة، مثال: 5د")
            return

        minutes = int(match.group(1))
        data["duration"] = minutes * 60
        data["remaining"] = data["duration"]
        data["current_speaker"] = data["speaker1"]
        data["step"] = "ready"

        await update.message.reply_text(
            f"✅ تم تسجيل المناظرة:\n"
            f"🎙️ {data['title']}\n"
            f"🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            "اكتب 'ابدأ الوقت' للبدء."
        )
        return

    # بدء الوقت
    if text == "ابدأ الوقت":
        data["running"] = True
        data["extra_mode"] = False
        data["extra_time"] = 0

        if chat_id in tasks:
            tasks[chat_id].cancel()

        tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))
        color = get_speaker_color(data, data["current_speaker"])
        await update.message.reply_text(f"▶️ بدأ الوقت للمتحدث: {color} {data['current_speaker']}")
        return

    # توقف واستئناف
    if text == "توقف":
        data["running"] = False
        await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت المتبقي: {format_time(data['remaining'])}")
        return

    if text == "استئناف":
        if data["running"]:
            await update.message.reply_text("المؤقت يعمل بالفعل.")
            return
        data["running"] = True
        if chat_id in tasks:
            tasks[chat_id].cancel()
        tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))
        await update.message.reply_text("▶️ تم استئناف المؤقت.")
        return

    # تبديل / تنازل
    if text in ["تبديل", "تنازل"]:
        prev_speaker = data["current_speaker"]
        next_speaker = data["speaker2"] if prev_speaker == data["speaker1"] else data["speaker1"]
        color_prev = get_speaker_color(data, prev_speaker)
        color_next = get_speaker_color(data, next_speaker)

        # حفظ التجاوز الكلي
        if prev_speaker == data["speaker1"]:
            data["total_extra"][1] += data.get("extra_time", 0)
        else:
            data["total_extra"][2] += data.get("extra_time", 0)

        added_time = data.get("extra_time", 0) if text == "تبديل" else 0
        data["current_speaker"] = next_speaker
        data["remaining"] = data["duration"] + added_time
        data["extra_time"] = 0
        data["extra_mode"] = False
        data["round"] += 1
        data["running"] = True

        if chat_id in tasks:
            tasks[chat_id].cancel()
        tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))

        if text == "تنازل":
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚨 تنازل {color_prev} {prev_speaker} عن المداخلة!\n🔁 الدور ينتقل الآن إلى: {color_next} {next_speaker}"
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔁 تم التبديل إلى: {color_next} {next_speaker}\n"
                     f"الوقت الزائد المضاف: +{format_time(added_time)}\n"
                     f"الوقت الإجمالي للمداخلة: {format_time(data['remaining'])}"
            )
        return

    # نهاية المناظرة
    if text == "نهاية":
        data["running"] = False
        if chat_id in tasks:
            tasks[chat_id].cancel()

        total_extra1 = format_time(data["total_extra"][1])
        total_extra2 = format_time(data["total_extra"][2])

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "━━━━━━━━━━━━━━━━━━\n"
                f"نهاية المناظرة – عرض النتائج\n"
                f"📊 المناظرة: {data['title']}\n\n"
                f"🟢 {data['speaker1']}\n"
                f"🔴 تجاوز الوقت: +{total_extra1}\n\n"
                f"🔵 {data['speaker2']}\n"
                f"🔴 تجاوز الوقت: +{total_extra2}\n"
                "━━━━━━━━━━━━━━━━━━"
            )
        )
        debate_data.pop(chat_id, None)
        return

    # أوامر أخرى
    if text == "حالة المناظرة":
        await send_debate_status(context, chat_id)
        return

    # إضافة / إنقاص / إعادة
    add_match = re.match(r"اضف\s*(\d+)([دث])", text)
    if add_match:
        amount = int(add_match.group(1))
        if add_match.group(2) == "د":
            amount *= 60
        data["remaining"] += amount
        await update.message.reply_text(f"✅ تم إضافة {format_time(amount)} للمتحدث الحالي.")
        return

    sub_match = re.match(r"انقص\s*(\d+)([دث])", text)
    if sub_match:
        amount = int(sub_match.group(1))
        if sub_match.group(2) == "د":
            amount *= 60
        data["remaining"] = max(0, data["remaining"] - amount)
        await update.message.reply_text(f"✅ تم إنقاص {format_time(amount)} من المتحدث الحالي.")
        return

    if text == "اعادة":
        data["remaining"] = data["duration"]
        data["extra_time"] = 0
        await update.message.reply_text(f"♻️ تم إعادة وقت المداخلة إلى {format_time(data['duration'])}")
        return

# =============================
# تشغيل البوت
# =============================
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

if __name__ == "__main__":
    application.run_polling()
