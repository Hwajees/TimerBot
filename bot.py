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
debate_data = {}  # كل chat_id له بياناته
tasks = {}        # كل chat_id له task واحدة للمؤقت

# =============================
# أدوات مساعدة
# =============================
def format_time(seconds, show_plus=False):
    """تحويل الثواني إلى صيغة 00:00 مع خيار إظهار علامة + للوقت الزائد"""
    sign = "+" if show_plus else ""
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    return f"{sign}{minutes:02d}:{seconds:02d}"

def convert_arabic_numbers(text):
    arabic_to_english = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return text.translate(arabic_to_english)

async def send_debate_status(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    speaker = data["current_speaker"]
    color = "🟢" if speaker == data["speaker1"] else "🔵"
    remain = max(0, data["remaining"])
    extra = data.get("extra_time", 0)
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n"
        f"👤 المتحدث الآن: {color} {speaker}\n"
        f"⏱️ الوقت المتبقي: {format_time(remain)}\n"
        f"⏳ الجولة: {data['round']}\n"
        f"🕐 الوقت الزائد: {format_time(extra, show_plus=True)}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=chat_id, text=text)

# =============================
# مؤقت المتحدث
# =============================
async def timer_task(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    last_alert = -1
    while chat_id in debate_data and data["running"]:
        await asyncio.sleep(1)
        if data["remaining"] > 0:
            data["remaining"] -= 1
            if 0 < data["remaining"] <= 30 and data["remaining"] % 10 == 0 and data["remaining"] != last_alert:
                last_alert = data["remaining"]
                color = "🟢" if data["current_speaker"] == data["speaker1"] else "🔵"
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ انتبه! {color} {data['current_speaker']} تبقى {format_time(data['remaining'])} على انتهاء المداخلة!"
                )
        else:
            # بدء الوقت الزائد
            if not data.get("extra_mode", False):
                data["extra_mode"] = True
                data["extra_time"] = 0
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 انتهى وقت {data['current_speaker']}!\n⏱️ بدأ حساب الوقت الزائد..."
                )

            await asyncio.sleep(1)
            data["extra_time"] += 1
            if data["extra_time"] <= 30:
                if data["extra_time"] % 10 == 0 or data["extra_time"] == 1:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⌛ الوقت الزائد للمتحدث الحالي 🔴 {data['current_speaker']}: {format_time(data['extra_time'], show_plus=True)}"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏱️ توقف وقت 🔴 {data['current_speaker']}!\n🚨 يجب تبديل المحاور..."
                )
                data["running"] = False
                break

# =============================
# معالجة الرسائل
# =============================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    text_conv = convert_arabic_numbers(text)

    chat_admins = await context.bot.get_chat_administrators(chat_id)
    if not any(admin.user.id == user.id for admin in chat_admins):
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
            "round": 1,
            "extra_time": 0,
            "extra_mode": False,
            "total_extra": {1: 0, 2: 0},
            "interventions": {1: 0, 2: 0},
            "total_time": {1: 0, 2: 0}
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
            f"🎙️ مناظرة: {data['title']}\n"
            f"👥 المحاورون: 🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            "اكتب 'ابدأ الوقت' للبدء."
        )
        return

    # ==================== أوامر بعد البدء ====================
    if text_conv == "ابدأ الوقت":
        data["running"] = True
        data["step"] = "running"
        data["extra_mode"] = False
        data["extra_time"] = 0
        current_index = 1 if data["current_speaker"] == data["speaker1"] else 2
        data["interventions"][current_index] += 1
        if chat_id in tasks:
            tasks[chat_id].cancel()
        tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))
        await update.message.reply_text(f"▶️ بدأ الوقت للمتحدث: {data['current_speaker']}")
        return

    if data["step"] == "running":
        if text_conv == "توقف":
            data["running"] = False
            await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت المتبقي: {format_time(data['remaining'])}")
            return

        if text_conv == "استئناف":
            if data["running"]:
                await update.message.reply_text("المؤقت يعمل بالفعل.")
                return
            data["running"] = True
            if chat_id in tasks:
                tasks[chat_id].cancel()
            tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))
            await update.message.reply_text("▶️ تم استئناف المؤقت.")
            return

        if text_conv in ["تبديل", "تنازل"]:
            prev_speaker = data["current_speaker"]
            next_speaker = data["speaker2"] if prev_speaker == data["speaker1"] else data["speaker1"]
            prev_index = 1 if prev_speaker == data["speaker1"] else 2
            next_index = 1 if next_speaker == data["speaker1"] else 2

            data["total_extra"][prev_index] += data.get("extra_time", 0)
            extra_text = format_time(data.get("extra_time", 0), show_plus=True)
            total_new = data["duration"] + data.get("extra_time", 0)

            if text_conv == "تنازل":
                data["current_speaker"] = next_speaker
                data["remaining"] = data["duration"]
                msg = f"🚨 تنازل 🟢 {prev_speaker} عن المداخلة!\n🔁 الدور ينتقل الآن إلى: 🔵 {next_speaker}"
            else:
                data["current_speaker"] = next_speaker
                data["remaining"] = total_new
                msg = (
                    f"🔁 تم التبديل إلى: 🔵 {next_speaker}\n"
                    f"الوقت الزائد المضاف: {extra_text}\n"
                    f"الوقت الإجمالي للمداخلة: {format_time(total_new)}"
                )

            data["round"] += 1
            data["extra_time"] = 0
            data["extra_mode"] = False
            data["running"] = True
            data["interventions"][next_index] += 1

            if chat_id in tasks:
                tasks[chat_id].cancel()
            tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))

            await context.bot.send_message(chat_id=chat_id, text=msg)
            return

        if text_conv == "حالة المناظرة":
            await send_debate_status(context, chat_id)
            return

        if text_conv == "نهاية":
            data["running"] = False
            if chat_id in tasks:
                tasks[chat_id].cancel()
                del tasks[chat_id]

            s1, s2 = data["speaker1"], data["speaker2"]
            t1, t2 = data["total_time"][1], data["total_time"][2]
            e1, e2 = data["total_extra"][1], data["total_extra"][2]
            total_time = t1 + t2

            summary = (
                "━━━━━━━━━━━━━━━━━━\n"
                "نهاية المناظرة – عرض النتائج\n"
                f"📊 المناظرة: {data['title']}\n\n"
                f"🟢 {s1}\n"
                f"🗣️ عدد المداخلات: {data['interventions'][1]}\n"
                f"⏱️ الوقت المستخدم: {format_time(t1)}\n"
                f"🔴 تجاوز الوقت: {format_time(e1, show_plus=True)}\n\n"
                f"🔵 {s2}\n"
                f"🗣️ عدد المداخلات: {data['interventions'][2]}\n"
                f"⏱️ الوقت المستخدم: {format_time(t2)}\n"
                f"🔴 تجاوز الوقت: {format_time(e2, show_plus=True)}\n\n"
                f"🕒 الوقت الكلي: {format_time(total_time)}\n"
                "━━━━━━━━━━━━━━━━━━"
            )

            await update.message.reply_text(summary)
            debate_data.pop(chat_id, None)
            return

# =============================
# تشغيل البوت
# =============================
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

if __name__ == "__main__":
    application.run_polling()
