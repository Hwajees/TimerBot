import os
import re
import time
import threading
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
timers = {}
lock = threading.Lock()

# =============================
# أدوات مساعدة
# =============================
def format_time_mmss(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

def is_admin(user_id, admins):
    return any(admin.user.id == user_id for admin in admins)

def convert_arabic_numbers(text):
    arabic_to_english = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return text.translate(arabic_to_english)

async def send_debate_status(context: ContextTypes.DEFAULT_TYPE, chat_id):
    data = debate_data[chat_id]
    speaker = data["current_speaker"]
    total = data["round"]
    remain = max(0, data["remaining"])
    extra = data.get("extra_time", 0)
    color = "🟢" if speaker == data["speaker1"] else "🔵"
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ مناظرة: {data['title']}\n"
        f"👤 المتحدث الآن: {color} {speaker}\n"
        f"⏱️ الوقت المتبقي: {format_time_mmss(remain)}\n"
        f"⏳ الجولة: {total}\n"
        f"🕐 الوقت الزائد: +{format_time_mmss(extra)}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=chat_id, text=text)

# =============================
# المؤقت
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
                if not data or not data["running"]:
                    continue

                # تناقص الوقت العادي
                if data["remaining"] > 0:
                    data["remaining"] -= 1
                    if 0 < data["remaining"] <= 30 and data["remaining"] % 10 == 0 and data["remaining"] != last_alert:
                        last_alert = data["remaining"]
                        color = "🟢" if data["current_speaker"] == data["speaker1"] else "🔵"
                        await send_message_safe(
                            f"⏳ انتبه! {color} {data['current_speaker']} تبقى {format_time_mmss(data['remaining'])} على انتهاء المداخلة!"
                        )

                # انتهاء الوقت العادي
                if data["remaining"] <= 0 and not data.get("extra_mode", False):
                    data["running"] = False
                    data["extra_mode"] = True
                    data["extra_time"] = 0
                    await send_message_safe(
                        f"🚨 انتهى وقت {data['current_speaker']}!\n⏱️ بدأ حساب الوقت الزائد..."
                    )

            # الوقت الزائد
            if data.get("extra_mode", False):
                await asyncio.sleep(10)
                with lock:
                    d = debate_data.get(chat_id)
                    if not d or not d.get("extra_mode", False):
                        continue
                    d["extra_time"] = d.get("extra_time", 0) + 10
                    if d["extra_time"] <= 30:
                        await send_message_safe(
                            f"⌛ الوقت الزائد للمتحدث الحالي 🔴 {d['current_speaker']}: +{format_time_mmss(d['extra_time'])}"
                        )
                    else:
                        await send_message_safe(
                            f"⏱️ توقف وقت {d['current_speaker']}!\n🚨 يجب تبديل المحاور..."
                        )
                        d["running"] = False

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
            "summary": { "speaker1": {"used":0, "over":0, "turns":0}, "speaker2":{"used":0,"over":0,"turns":0} }
        }
        await update.message.reply_text(
            "تم استدعاء البوت! أرسل بيانات المناظرة بالترتيب مفصولة بسطر لكل واحد:\n"
            "1. عنوان المناظرة\n2. المحاور الأول\n3. المحاور الثاني\n4. الوقت (مثال: 5د)"
        )
        return

    if chat_id not in debate_data:
        return

    data = debate_data[chat_id]

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
            f"👤 المحاورون: 🟢 {data['speaker1']} | 🔵 {data['speaker2']}\n"
            f"⏱️ الوقت لكل مداخلة: {minutes}د\n"
            "يمكنك تعديل أي عنصر باستخدام: 'تعديل عنوان/محاور1/محاور2/وقت القيمة الجديدة'\n"
            "اكتب 'ابدأ الوقت' للبدء."
        )
        return

    # ==================== تعديل البيانات ====================
    if text_conv.startswith("تعديل "):
        parts = text_conv[6:].split(" ", 1)
        if len(parts) == 2:
            field, new_val = parts
            new_val = new_val.strip()
            if field in ["عنوان", "محاور1", "محاور2", "وقت"]:
                if field == "عنوان": data["title"] = new_val
                elif field == "محاور1": data["speaker1"] = new_val
                elif field == "محاور2": data["speaker2"] = new_val
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

    # ==================== أوامر المؤقت ====================
    if text_conv == "ابدأ الوقت":
        data["running"] = True
        data["step"] = "running"
        data["extra_mode"] = False
        data["extra_time"] = 0
        thread = threading.Thread(target=timer_thread, args=(context, chat_id))
        thread.start()
        timers[chat_id] = thread
        await update.message.reply_text(f"▶️ بدأ الوقت للمتحدث: 🟢 {data['current_speaker']}")
        return

    if data["step"] == "running":
        if text_conv == "توقف":
            data["running"] = False
            await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت المتبقي: {format_time_mmss(data['remaining'])}")
            return

        if text_conv == "استئناف":
            if data["running"]:
                await update.message.reply_text("المؤقت يعمل بالفعل.")
                return
            data["running"] = True
            thread = threading.Thread(target=timer_thread, args=(context, chat_id))
            thread.start()
            timers[chat_id] = thread
            await update.message.reply_text("▶️ تم استئناف المؤقت.")
            return

        # ==================== تبديل و تنازل ====================
        if text_conv in ["تبديل", "تنازل"]:
            prev_speaker = data["current_speaker"]
            next_speaker = data["speaker2"] if prev_speaker == data["speaker1"] else data["speaker1"]
            prev_color = "🟢" if prev_speaker==data["speaker1"] else "🔵"
            next_color = "🟢" if next_speaker==data["speaker1"] else "🔵"

            if text_conv=="تبديل":
                total_time = data["duration"] + data.get("extra_time",0)
                extra_added = data.get("extra_time",0)
                data["current_speaker"] = next_speaker
                data["remaining"] = total_time
                data["round"] +=1
                data["extra_time"] = 0
                data["extra_mode"] = False
                data["running"] = True

                if chat_id in timers:
                    data["running"] = False
                    timers[chat_id].join()
                    del timers[chat_id]
                thread = threading.Thread(target=timer_thread, args=(context, chat_id))
                thread.start()
                timers[chat_id] = thread

                await context.bot.send_message(chat_id=chat_id,
                    text=f"🔁 تم التبديل إلى: {next_color} {next_speaker}\n"
                         f"الوقت الزائد المضاف: +{format_time_mmss(extra_added)}\n"
                         f"الوقت الإجمالي للمداخلة: {format_time_mmss(total_time)}")
            else: # تنازل
                data["current_speaker"] = next_speaker
                data["remaining"] = data["duration"]
                data["round"] +=1
                data["extra_time"] = 0
                data["extra_mode"] = False
                data["running"] = True
                if chat_id in timers:
                    data["running"] = False
                    timers[chat_id].join()
                    del timers[chat_id]
                thread = threading.Thread(target=timer_thread, args=(context, chat_id))
                thread.start()
                timers[chat_id] = thread

                await context.bot.send_message(chat_id=chat_id,
                    text=f"🚨 تنازل {prev_color} {prev_speaker} عن المداخلة!\n"
                         f"🔁 الدور ينتقل الآن إلى: {next_color} {next_speaker}")
            return

        # ==================== حالة المناظرة ====================
        if text_conv == "حالة المناظرة":
            await send_debate_status(context, chat_id)
            return

        # ==================== نهاية المناظرة ====================
        if text_conv == "نهاية":
            s1 = data["speaker1"]
            s2 = data["speaker2"]
            used1 = data["summary"]["speaker1"]["used"] + data["duration"]
            used2 = data["summary"]["speaker2"]["used"] + data["duration"]
            over1 = data["summary"]["speaker1"]["over"]
            over2 = data["summary"]["speaker2"]["over"]
            total_time = used1 + used2
            text = (
                "━━━━━━━━━━━━━━━━━━\n"
                "نهاية المناظرة – عرض النتائج\n"
                f"📊 المناظرة: {data['title']}\n\n"
                f"🟢 {s1}\n"
                f"🗣️ عدد المداخلات: {data['summary']['speaker1']['turns']}\n"
                f"⏱️ الوقت المستخدم: {format_time_mmss(used1)}\n"
                f"🔴 تجاوز الوقت: +{format_time_mmss(over1)} \n\n"
                f"🔵 {s2}\n"
                f"🗣️ عدد المداخلات: {data['summary']['speaker2']['turns']}\n"
                f"⏱️ الوقت المستخدم: {format_time_mmss(used2)}\n"
                f"🔴 تجاوز الوقت: +{format_time_mmss(over2)} \n\n"
                f"🕒 الوقت الكلي: {format_time_mmss(total_time)}\n"
                "━━━━━━━━━━━━━━━━━━"
            )
            await update.message.reply_text(text)
            debate_data.pop(chat_id, None)
            return

        # ==================== إضافة / إنقاص الوقت ====================
        add_match = re.match(r"اضف\s*(\d+)([دث])", text_conv)
        if add_match:
            amount = int(add_match.group(1))
            unit = add_match.group(2)
            if unit=="د": amount*=60
            data["remaining"] += amount
            await update.message.reply_text(f"✅ تم إضافة {amount if unit=='ث' else amount//60}{unit} للمتحدث الحالي")
            return

        sub_match = re.match(r"انقص\s*(\d+)([دث])", text_conv)
        if sub_match:
            amount = int(sub_match.group(1))
            unit = sub_match.group(2)
            if unit=="د": amount*=60
            data["remaining"] = max(0, data["remaining"] - amount)
            await update.message.reply_text(f"✅ تم إنقاص {amount if unit=='ث' else amount//60}{unit} من المتحدث الحالي")
            return

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
