import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# بيانات الجلسة
session_data = {
    "active": False,
    "creator_id": None,
    "title": None,
    "speaker1": None,
    "speaker2": None,
    "time_per_turn": None,
    "current_speaker": None,
    "turn_start": None,
    "turn_remaining": None,
    "round": 1,
    "logs": []
}

# مساعدة: تحويل نص الوقت إلى ثواني
def parse_time(text):
    text = text.strip().lower()
    seconds = 0
    if "د" in text:
        seconds += int(text.replace("د", "")) * 60
    if "ث" in text:
        seconds += int(text.replace("ث", ""))
    return seconds

# تنسيق الرسائل
def format_status():
    speaker = session_data["current_speaker"]
    remaining = str(timedelta(seconds=session_data["turn_remaining"]))
    return f"""━━━━━━━━━━━━━━━━━━
🎙️ مناظرة: {session_data['title']}

👤 المتحدث الآن: {speaker}
⏱️ الوقت المتبقي: {remaining}
⏳ الجولة: {session_data['round']}
━━━━━━━━━━━━━━━━━━"""

# التحقق من المشرف
async def is_admin(update: Update):
    if session_data["creator_id"] is None:
        return True
    member = await update.effective_chat.get_member(update.effective_user.id)
    return member.status in ["administrator", "creator"]

# التحقق من صلاحية الأمر
async def check_permission(update: Update):
    if update.effective_user.id != session_data["creator_id"]:
        if not await is_admin(update):
            return False
    return True

# بدء العد
async def start_turn(context: ContextTypes.DEFAULT_TYPE):
    while session_data["turn_remaining"] > 0:
        await asyncio.sleep(1)
        session_data["turn_remaining"] -= 1
        if session_data["turn_remaining"] % 10 == 0:
            await context.bot.send_message(chat_id=GROUP_ID, text=format_status())
    # انتهاء الوقت
    await context.bot.send_message(chat_id=GROUP_ID, text=f"🚨 انتهى وقت المحاور!\n👤 {session_data['current_speaker']} أكمل وقته المحدد")
    # التبديل تلقائي
    await switch_speaker(context)

async def switch_speaker(context: ContextTypes.DEFAULT_TYPE):
    if session_data["current_speaker"] == session_data["speaker1"]:
        session_data["current_speaker"] = session_data["speaker2"]
    else:
        session_data["current_speaker"] = session_data["speaker1"]
    session_data["turn_start"] = datetime.now()
    session_data["turn_remaining"] = session_data["time_per_turn"]
    session_data["round"] += 1
    await context.bot.send_message(chat_id=GROUP_ID, text=format_status())
    asyncio.create_task(start_turn(context))

# التعامل مع الرسائل
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    text = update.message.text.strip()
    
    # تسجيل بيانات الجلسة الأولية
    if not session_data["active"]:
        if session_data["creator_id"] is None:
            session_data["creator_id"] = update.effective_user.id
        if session_data["title"] is None:
            session_data["title"] = text
            await update.message.reply_text(f"تم تسجيل العنوان: {text}\nالآن أرسل اسم المحاور الأول:")
            return
        if session_data["speaker1"] is None:
            session_data["speaker1"] = text
            await update.message.reply_text(f"تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:")
            return
        if session_data["speaker2"] is None:
            session_data["speaker2"] = text
            await update.message.reply_text(f"تم تسجيل المحاور الثاني: {text}\nأدخل الوقت لكل مداخلة (مثال: 3د):")
            return
        if session_data["time_per_turn"] is None:
            session_data["time_per_turn"] = parse_time(text)
            await update.message.reply_text(
                f"تم تحديد الوقت: {text}.\nاكتب 'ابدأ الوقت' للبدء."
            )
            session_data["active"] = True
            session_data["current_speaker"] = session_data["speaker1"]
            session_data["turn_remaining"] = session_data["time_per_turn"]
            session_data["turn_start"] = datetime.now()
            return
    
    # أوامر أثناء الجلسة
    if not await check_permission(update):
        return

    if text == "ابدأ الوقت":
        await update.message.reply_text(f"⏳ تم بدء المناظرة!\n{format_status()}")
        asyncio.create_task(start_turn(context))
    elif text == "تبديل":
        await switch_speaker(context)
    elif text == "توقف":
        # سيضيف التوقف مستقبلًا
        await update.message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.")
    elif text == "استئناف":
        # استئناف
        await update.message.reply_text(f"▶️ تم استئناف المؤقت.\n{format_status()}")
    elif text == "تنازل":
        await switch_speaker(context)
    elif text.startswith("اضف"):
        # إضافة وقت
        value = parse_time(text.replace("اضف", ""))
        session_data["turn_remaining"] += value
        await update.message.reply_text(f"تم إضافة الوقت: {text}\n{format_status()}")
    elif text.startswith("انقص"):
        value = parse_time(text.replace("انقص", ""))
        session_data["turn_remaining"] = max(0, session_data["turn_remaining"] - value)
        await update.message.reply_text(f"تم إنقاص الوقت: {text}\n{format_status()}")
    elif text == "اعادة":
        session_data["turn_remaining"] = session_data["time_per_turn"]
        session_data["turn_start"] = datetime.now()
        await update.message.reply_text(f"🔁 إعادة وقت المداخلة من البداية.\n{format_status()}")
    elif text == "نهاية":
        await update.message.reply_text("📊 نتائج المناظرة:")
        # هنا يمكن إضافة تفاصيل الوقت لكل محاور
        session_data["active"] = False

# إعداد البوت
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

# Webhook
async def main():
    await app.bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")
    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # يسمح بإعادة استخدام حلقة الأحداث الحالية
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
