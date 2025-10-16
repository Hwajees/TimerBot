import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# --------------------------
# المتغيرات من Environment
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))
# --------------------------

# الحالة الحالية للمناظرة
debate_data = {
    "active": False,            # هل جلسة إدخال البيانات نشطة
    "initiator": None,          # المشرف الأول الذي بدأ الجلسة
    "title": "",
    "speaker1": "",
    "speaker2": "",
    "time_per_turn": 0,         # بالثواني
    "current_speaker": "",
    "current_turn_time": 0,
    "remaining_time": 0,
    "round": 1,
    "turns_count": { },
    "over_time": 0,
}

# أوامر استدعاء البوت
trigger_words = [
    "بوت المؤقت", "المؤقت", "بوت الساعة",
    "بوت الساعه", "الساعة", "الساعه"
]

# --------------------------
# وظائف مساعدة
# --------------------------

async def send_debate_status(update: Update):
    speaker_emoji = "🟢" if debate_data["current_speaker"] == debate_data["speaker1"] else "🔵"
    msg = f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎙️ مناظرة: {debate_data['title']}\n\n"
    msg += f"👤 المتحدث الآن: {speaker_emoji} {debate_data['current_speaker']}\n"
    minutes = debate_data["remaining_time"] // 60
    seconds = debate_data["remaining_time"] % 60
    msg += f"⏱️ الوقت المتبقي: {minutes:02d}:{seconds:02d}\n"
    msg += f"⏳ الجولة: {debate_data['round']}\n"
    if debate_data["over_time"] > 0:
        ot_min = debate_data["over_time"] // 60
        ot_sec = debate_data["over_time"] % 60
        msg += f"🔴 تجاوز الوقت: +{ot_min:02d}:{ot_sec:02d}\n"
    msg += "━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg)

async def timer_loop(context: ContextTypes.DEFAULT_TYPE):
    while debate_data["active"]:
        await asyncio.sleep(1)
        if debate_data["remaining_time"] > 0:
            debate_data["remaining_time"] -= 1
        else:
            debate_data["over_time"] += 1
        # يمكن هنا تحديث الرسالة الدورية إذا أحببت

# --------------------------
# التعامل مع الرسائل
# --------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global debate_data
    message = update.message.text.strip()
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # تجاهل أي رسائل خارج المجموعة المحددة
    if chat_id != GROUP_ID:
        return

    # --------------------------
    # استدعاء البوت
    # --------------------------
    if not debate_data["active"] and any(word in message for word in trigger_words):
        debate_data["initiator"] = user_id
        debate_data["active"] = True
        debate_data["turns_count"] = { }
        await update.message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    # --------------------------
    # التعامل مع المشرف الأول أثناء تسجيل البيانات
    # --------------------------
    if debate_data["active"] and user_id == debate_data["initiator"]:
        # تسجيل البيانات
        if debate_data["title"] == "":
            if message.lower().startswith("تعديل العنوان:"):
                debate_data["title"] = message.split(":",1)[1].strip()
                await update.message.reply_text(f"تم تعديل العنوان: {debate_data['title']}")
            else:
                debate_data["title"] = message
                await update.message.reply_text(f"تم تسجيل عنوان المناظرة: {debate_data['title']}\nالآن أدخل اسم المحاور الأول:")
            return
        elif debate_data["speaker1"] == "":
            if message.lower().startswith("تعديل محاور1:"):
                debate_data["speaker1"] = message.split(":",1)[1].strip()
                await update.message.reply_text(f"تم تعديل اسم المحاور الأول: {debate_data['speaker1']}")
            else:
                debate_data["speaker1"] = message
                await update.message.reply_text(f"تم تسجيل المحاور الأول: {debate_data['speaker1']}\nالآن أدخل اسم المحاور الثاني:")
            return
        elif debate_data["speaker2"] == "":
            if message.lower().startswith("تعديل محاور2:"):
                debate_data["speaker2"] = message.split(":",1)[1].strip()
                await update.message.reply_text(f"تم تعديل اسم المحاور الثاني: {debate_data['speaker2']}")
            else:
                debate_data["speaker2"] = message
                await update.message.reply_text(f"تم تسجيل المحاور الثاني: {debate_data['speaker2']}\nالآن أدخل الوقت لكل مداخلة بالدقائق:")
            return
        elif debate_data["time_per_turn"] == 0:
            if message.lower().startswith("تعديل الوقت:"):
                mins = int(message.split(":",1)[1].strip().replace("د",""))
                debate_data["time_per_turn"] = mins * 60
                await update.message.reply_text(f"تم تعديل الوقت لكل مداخلة: {mins} دقائق\nاكتب 'ابدأ الوقت' لبدء المناظرة.")
            else:
                mins = int(message.replace("د",""))
                debate_data["time_per_turn"] = mins * 60
                await update.message.reply_text(f"تم تسجيل الوقت لكل مداخلة: {mins} دقائق\nاكتب 'ابدأ الوقت' لبدء المناظرة.")
            return
        elif message == "ابدأ الوقت":
            debate_data["current_speaker"] = debate_data["speaker1"]
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            debate_data["over_time"] = 0
            debate_data["turns_count"] = {debate_data["speaker1"]:0, debate_data["speaker2"]:0}
            await update.message.reply_text("تم بدء المناظرة!")
            await send_debate_status(update)
            context.application.create_task(timer_loop(context))
            return

    # --------------------------
    # بعد بدء المناظرة - أوامر بدون /
    # --------------------------
    if debate_data["current_speaker"] != "":
        # تبديل المتحدث
        if message == "تبديل":
            debate_data["round"] += 1
            debate_data["over_time"] = 0
            debate_data["turns_count"][debate_data["current_speaker"]] += 1
            debate_data["current_speaker"] = debate_data["speaker2"] if debate_data["current_speaker"] == debate_data["speaker1"] else debate_data["speaker1"]
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            await send_debate_status(update)
            return

        # إيقاف مؤقت
        if message == "توقف":
            debate_data["active"] = False
            await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت الحالي: {debate_data['remaining_time']//60:02d}:{debate_data['remaining_time']%60:02d}\n⏳ المتبقي: {debate_data['time_per_turn']//60:02d}:{debate_data['time_per_turn']%60:02d}")
            return

        # استئناف
        if message == "استئناف":
            debate_data["active"] = True
            context.application.create_task(timer_loop(context))
            await update.message.reply_text(f"▶️ تم استئناف المؤقت.\n⏱️ الوقت الحالي: {debate_data['remaining_time']//60:02d}:{debate_data['remaining_time']%60:02d}\n⏳ المتبقي: {debate_data['time_per_turn']//60:02d}:{debate_data['time_per_turn']%60:02d}\nالمتحدث الآن: {debate_data['current_speaker']}")
            return

        # تنازل
        if message == "تنازل":
            debate_data["turns_count"][debate_data["current_speaker"]] += 1
            debate_data["over_time"] = 0
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            debate_data["current_speaker"] = debate_data["speaker2"] if debate_data["current_speaker"] == debate_data["speaker1"] else debate_data["speaker1"]
            await send_debate_status(update)
            return

        # إعادة وقت المداخلة
        if message == "اعادة":
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            debate_data["over_time"] = 0
            await update.message.reply_text(f"🔄 تم إعادة وقت المداخلة من البداية.\nالمتحدث الآن: {debate_data['current_speaker']}\nالوقت المحدد: {debate_data['time_per_turn']//60}د")
            return

        # نهاية المناظرة
        if message == "نهاية":
            msg = f"📊 نتائج المناظرة: {debate_data['title']}\n\n"
            for speaker in [debate_data["speaker1"], debate_data["speaker2"]]:
                turns = debate_data["turns_count"].get(speaker,0)
                used_time = (turns * debate_data["time_per_turn"] + (debate_data["time_per_turn"] - debate_data["remaining_time"]))//1
                minutes = int(used_time // 60)
                seconds = int(used_time % 60)
                msg += f"{'🟢' if speaker == debate_data['speaker1'] else '🔵'} {speaker}\n"
                msg += f"🗣️ عدد المداخلات: {turns}\n"
                msg += f"⏱️ الوقت المستخدم: {minutes:02d}:{seconds:02d} دقيقة\n\n"
            total_time = sum([turns*debate_data["time_per_turn"] for turns in debate_data["turns_count"].values()])//1
            msg += f"🕒 الوقت الكلي: {int(total_time//60):02d}:{int(total_time%60):02d} دقيقة\n━━━━━━━━━━━━━━━━━━"
            await update.message.reply_text(msg)
            # إعادة الحالة للانتظار
            debate_data["active"] = False
            debate_data["initiator"] = None
            debate_data["title"] = ""
            debate_data["speaker1"] = ""
            debate_data["speaker2"] = ""
            debate_data["current_speaker"] = ""
            debate_data["current_turn_time"] = 0
            debate_data["remaining_time"] = 0
            debate_data["round"] = 1
            debate_data["turns_count"] = {}
            debate_data["over_time"] = 0
            return

        # إضافة أو إنقاص الوقت
        if message.startswith("اضف") or message.startswith("انقص"):
            action = "اضف" if message.startswith("اضف") else "انقص"
            try:
                num = int(''.join(filter(str.isdigit, message)))
                if "ث" in message:
                    secs = num
                elif "د" in message:
                    secs = num*60
                else:
                    await update.message.reply_text("⚠️ صيغة غير صحيحة! استخدم ث للثواني أو د للدقائق.")
                    return
                if action=="اضف":
                    debate_data["remaining_time"] += secs
                else:
                    debate_data["remaining_time"] -= secs
                    if debate_data["remaining_time"] < 0:
                        debate_data["over_time"] += abs(debate_data["remaining_time"])
                        debate_data["remaining_time"]=0
                await update.message.reply_text(f"⏱️ تم {action} الوقت. الوقت الحالي للمتحدث: {debate_data['remaining_time']//60:02d}:{debate_data['remaining_time']%60:02d}")
            except:
                await update.message.reply_text("⚠️ صيغة غير صحيحة! استخدم مثل: اضف ٣٠ث أو انقص ٢د")
            return

# --------------------------
# تشغيل البوت
# --------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("البوت يعمل...")
app.run_polling()
