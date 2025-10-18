import os
import re
import threading
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
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n"
        f"👤 المتحدث الآن: {data['current_speaker']}\n"
        f"⏱️ الوقت المتبقي: {format_time(max(0, data['remaining']))}\n"
        f"⏳ الجولة: {data['round']}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=chat_id, text=text)

# =============================
# المؤقت لكل مناظرة
# =============================
def timer_thread(context: ContextTypes.DEFAULT_TYPE, chat_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def send_message_safe(text):
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            pass

    async def timer_loop():
        last_alert = -1

        while chat_id in debate_data:
            await asyncio.sleep(1)
            with lock:
                data = debate_data.get(chat_id)
                if not data or not data.get("running"):
                    continue

                # تناقص الوقت
                data["remaining"] -= 1

                # 🔹 تنبيه آخر 30 ثانية
                if 0 < data["remaining"] <= 30 and data["remaining"] % 10 == 0 and data["remaining"] != last_alert:
                    last_alert = data["remaining"]
                    await send_message_safe(
                        f"⏳ انتبه! {data['current_speaker']} تبقى {format_time(data['remaining'])} على انتهاء المداخلة!"
                    )

                # 🔹 انتهاء الوقت وبدء الوقت الزائد
                if data["remaining"] <= 0 and not data.get("extra_mode", False):
                    data["running"] = False
                    data["extra_mode"] = True
                    data["extra_time"] = 0
                    await send_message_safe(
                        f"🚨 انتهى وقت {data['current_speaker']}!\n⏱️ بدأ حساب الوقت الزائد..."
                    )

            # 🔹 معالجة الوقت الزائد
            with lock:
                data = debate_data.get(chat_id)
                if not data:
                    break
                if data.get("extra_mode", False) and not data["running"]:
                    data["extra_time"] = data.get("extra_time", 0) + 10

            if data.get("extra_mode", False) and not data["running"]:
                await asyncio.sleep(10)
                with lock:
                    d = debate_data.get(chat_id)
                    if not d or d.get("running") or not d.get("extra_mode", False):
                        continue
                    await send_message_safe(
                        f"⌛ الوقت الزائد للمتحدث الحالي {d['current_speaker']}: {format_time(d['extra_time'])}"
                    )

    loop.run_until_complete(timer_loop())
    loop.close()

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
            "round": 1,
            "extra_mode": False,
            "extra_time": 0
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
        data["step"] = "running"

        # بدء Thread واحد للمؤقت
        thread = threading.Thread(target=timer_thread, args=(context, chat_id))
        thread.start()
        timers[chat_id] = thread

        await update.message.reply_text(
            f"✅ تم تسجيل البيانات:\n"
            f"🎙️ مناظرة: {data['title']}\n"
            f"👤 المحاورون: 🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            "يمكنك استخدام الأوامر:\n"
            "'تبديل' | 'تنازل' | 'اعادة' | 'اضف 5ث/5د' | 'انقص 5ث/5د' | 'حالة المناظرة' | 'نهاية'"
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
                    data["speaker1"] = new_val
                elif field == "محاور2":
                    data["speaker2"] = new_val
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

    # ==================== أوامر أثناء المناظرة ====================
    if data["step"] == "running":
        # توقف واستئناف
        if text_conv == "توقف":
            data["running"] = False
            await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت المتبقي: {format_time(data['remaining'])}")
            return
        if text_conv == "استئناف":
            if data["running"]:
                await update.message.reply_text("المؤقت يعمل بالفعل.")
                return
            data["running"] = True
            await update.message.reply_text("▶️ تم استئناف المؤقت.")
            return

        # تبديل المتحدث
        if text_conv == "تبديل":
            data["current_speaker"] = data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
            data["remaining"] = data["duration"]
            data["round"] += 1
            data["running"] = True
            data["extra_mode"] = False
            await update.message.reply_text(f"🔁 تم التبديل إلى: {data['current_speaker']}")
            return

        # تنازل
        if text_conv == "تنازل":
            next_speaker = data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
            data["current_speaker"] = next_speaker
            data["remaining"] = data["duration"]
            data["round"] += 1
            data["running"] = True
            data["extra_mode"] = False
            await update.message.reply_text(
                f"🚨 تنازل {user.first_name} عن المداخلة!\n🔁 الدور ينتقل الآن إلى: {next_speaker}"
            )
            return

        # اعادة الوقت
        if text_conv == "اعادة":
            data["remaining"] = data["duration"]
            await update.message.reply_text(f"♻️ تم إعادة وقت المداخلة للمتحدث الحالي إلى {data['duration']//60}د")
            return

        # اضافة/انقاص الوقت
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

        # حالة المناظرة
        if text_conv == "حالة المناظرة":
            await send_debate_status(context, chat_id)
            return

        # إنهاء المناظرة
        if text_conv == "نهاية":
            await update.message.reply_text("📊 تم إنهاء المناظرة.")
            debate_data.pop(chat_id, None)
            return

# =============================
# تشغيل البوت
# =============================
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

if __name__ == "__main__":
    application.run_polling()
