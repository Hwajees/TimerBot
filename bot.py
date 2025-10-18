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
def format_time(seconds):
    sign = "+" if seconds >= 0 else "-"
    seconds = abs(int(seconds))
    return f"{sign}{seconds//60:02}:{seconds%60:02}"

def format_time_display(seconds):
    # للعرض بدون +
    return f"{seconds//60:02}:{seconds%60:02}"

def convert_arabic_numbers(text):
    arabic_to_english = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return text.translate(arabic_to_english)

async def send_debate_status(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    speaker = data["current_speaker"]
    remain = max(0, data["remaining"])
    extra = data.get("extra_time", 0)
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n"
        f"👤 المتحدث الآن: {speaker}\n"
        f"⏱️ الوقت المتبقي: {format_time_display(remain)}\n"
        f"⏳ الجولة: {data['round']}\n"
        f"🕐 الوقت الزائد: {format_time_display(extra)}\n"
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
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ انتبه! {data['current_speaker']} تبقى {format_time_display(data['remaining'])} على انتهاء المداخلة!"
                )
        else:
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
                        text=f"⌛ الوقت الزائد للمتحدث الحالي {data['current_speaker']}: +{format_time_display(data['extra_time'])}"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏱️ توقف وقت {data['current_speaker']}!\n🚨 يجب تبديل المحاور..."
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
            "summary": {}
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

        # تهيئة summary لكل محاور
        data["summary"][data["speaker1"]] = {"used": 0, "over": 0, "turns": 0}
        data["summary"][data["speaker2"]] = {"used": 0, "over": 0, "turns": 0}

        await update.message.reply_text(
            f"✅ تم تسجيل البيانات:\n"
            f"🎙️ مناظرة: {data['title']}\n"
            f"👤 المحاورون: 🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            "يمكنك تعديل أي عنصر باستخدام: 'تعديل عنوان/محاور1/محاور2/وقت القيمة الجديدة'\n"
            "اكتب 'ابدأ الوقت' للبدء."
        )
        return

    # ==================== أوامر تعديل البيانات ====================
    if text_conv.startswith("تعديل "):
        parts = text_conv[6:].split(" ", 1)
        if len(parts) == 2:
            field, new_val = parts
            new_val = new_val.strip()
            if field in ["عنوان", "محاور1", "محاور2", "وقت"]:
                if field == "عنوان":
                    data["title"] = new_val
                elif field == "محاور1":
                    old_name = data["speaker1"]
                    data["speaker1"] = new_val
                    if old_name in data["summary"]:
                        data["summary"][new_val] = data["summary"].pop(old_name)
                    else:
                        data["summary"][new_val] = {"used": 0, "over": 0, "turns": 0}
                elif field == "محاور2":
                    old_name = data["speaker2"]
                    data["speaker2"] = new_val
                    if old_name in data["summary"]:
                        data["summary"][new_val] = data["summary"].pop(old_name)
                    else:
                        data["summary"][new_val] = {"used": 0, "over": 0, "turns": 0}
                elif field == "وقت":
                    match = re.match(r"(\d+)\s*د", convert_arabic_numbers(new_val))
                    if not match:
                        await update.message.reply_text("❌ صيغة الوقت غير صحيحة، مثال: 5د")
                        return
                    minutes = int(match.group(1))
                    data["duration"] = minutes * 60
                    data["remaining"] = data["duration"]
                await update.message.reply_text(f"✅ تم تعديل {field} إلى: {new_val}")
                return
        await update.message.reply_text("❌ صيغة الأمر غير صحيحة.")
        return

    # ==================== أوامر بعد البدء ====================
    if text_conv == "ابدأ الوقت":
        data["running"] = True
        data["step"] = "running"
        data["extra_mode"] = False
        data["extra_time"] = 0
        if chat_id in tasks:
            tasks[chat_id].cancel()
        tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))
        await update.message.reply_text(f"▶️ بدأ الوقت للمتحدث: {data['current_speaker']}")
        return

    if data["step"] == "running":
        # أمر التوقف
        if text_conv == "توقف":
            data["running"] = False
            await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت المتبقي: {format_time_display(data['remaining'])}")
            return
        # استئناف
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
        # تبديل أو تنازل
        if text_conv in ["تبديل", "تنازل"]:
            prev_speaker = data["current_speaker"]
            next_speaker = data["speaker2"] if prev_speaker == data["speaker1"] else data["speaker1"]
            used_time = data["duration"] - data["remaining"]
            over_time = max(0, data.get("extra_time", 0))
            # تحديث summary للمتحدث السابق
            if prev_speaker not in data["summary"]:
                data["summary"][prev_speaker] = {"used": 0, "over": 0, "turns": 0}
            data["summary"][prev_speaker]["used"] += used_time
            data["summary"][prev_speaker]["over"] += over_time
            data["summary"][prev_speaker]["turns"] += 1
            # الانتقال للمتحدث الجديد
            data["current_speaker"] = next_speaker
            data["remaining"] = data["duration"]
            data["extra_time"] = 0
            data["extra_mode"] = False
            data["round"] += 1
            data["running"] = True
            if chat_id in tasks:
                tasks[chat_id].cancel()
            tasks[chat_id] = asyncio.create_task(timer_task(context, chat_id))
            # الرسائل
            if text_conv == "تنازل":
                await context.bot.send_message(chat_id=chat_id,
                    text=f"🚨 تنازل {prev_speaker} عن المداخلة!\n🔁 الدور ينتقل الآن إلى: {next_speaker}")
            else:
                await context.bot.send_message(chat_id=chat_id,
                    text=f"🔁 تم التبديل إلى: {next_speaker}\nالوقت الإجمالي للمداخلة: {format_time_display(data['duration'] + over_time)}")
            return

        # حالة المناظرة
        if text_conv == "حالة المناظرة":
            await send_debate_status(context, chat_id)
            return

        # إنهاء المناظرة
        if text_conv == "نهاية":
            data["running"] = False
            if chat_id in tasks:
                tasks[chat_id].cancel()
                del tasks[chat_id]
            # إعداد ملخص جميل للنهاية
            total_time = 0
            summary_text = f"━━━━━━━━━━━━━━━━━━\nنهاية المناظرة – عرض النتائج\n📊 المناظرة: {data['title']}\n\n"
            for speaker, sdata in data["summary"].items():
                summary_text += f"{'🟢' if speaker==data['speaker1'] else '🔵'} {speaker}\n"
                summary_text += f"🗣️ عدد المداخلات: {sdata['turns']}\n"
                summary_text += f"⏱️ الوقت المستخدم: {format_time_display(sdata['used'])}\n"
                summary_text += f"🔴 تجاوز الوقت: +{format_time_display(sdata['over'])} \n\n"
                total_time += sdata['used'] + sdata['over']
            summary_text += f"🕒 الوقت الكلي: {format_time_display(total_time)}\n━━━━━━━━━━━━━━━━━━"
            await update.message.reply_text(summary_text)
            debate_data.pop(chat_id, None)
            return

        # إضافة الوقت
        add_match = re.match(r"اضف\s*(\d+)([دث])", text_conv)
        if add_match:
            amount = int(add_match.group(1))
            unit = add_match.group(2)
            if unit == "د":
                amount *= 60
            data["remaining"] += amount
            await update.message.reply_text(f"✅ تم إضافة {amount if unit=='ث' else amount//60}{unit} للمتحدث الحالي")
            return
        # إنقاص الوقت
        sub_match = re.match(r"انقص\s*(\d+)([دث])", text_conv)
        if sub_match:
            amount = int(sub_match.group(1))
            unit = sub_match.group(2)
            if unit == "د":
                amount *= 60
            data["remaining"] = max(0, data["remaining"] - amount)
            await update.message.reply_text(f"✅ تم إنقاص {amount if unit=='ث' else amount//60}{unit} من المتحدث الحالي")
            return
        # إعادة الوقت
        if text_conv == "اعادة":
            data["remaining"] = data["duration"]
            data["extra_time"] = 0
            data["extra_mode"] = False
            await update.message.reply_text(f"♻️ تم إعادة وقت المداخلة للمتحدث الحالي إلى {data['duration']//60}د")
            return

# =============================
# تشغيل البوت
# =============================
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

if __name__ == "__main__":
    application.run_polling()
