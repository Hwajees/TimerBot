import os
import asyncio
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Bot, Update, ChatMember
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters

# ------------------------------
# إعداد المتغيرات البيئية
# ------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ------------------------------
# إعداد Flask والبوت
# ------------------------------
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot=bot, update_queue=None, workers=0, use_context=True)

# ------------------------------
# حالة الجلسة والمتغيرات
# ------------------------------
session = {
    "active": False,
    "creator_id": None,
    "debate_title": None,
    "speaker1": None,
    "speaker2": None,
    "time_per_turn": None,
    "current_speaker": None,
    "remaining_time": None,
    "round": 1,
    "timer_running": False,
    "timer_task": None,
    "turn_start_time": None
}

# ------------------------------
# الأدوات المساعدة
# ------------------------------
def format_time(seconds):
    minutes, sec = divmod(seconds, 60)
    return f"{minutes:02d}:{sec:02d}"

def is_admin(user_id):
    return user_id == session.get("creator_id") or session.get("creator_id") is not None

async def send_group_message(text):
    await bot.send_message(chat_id=GROUP_ID, text=text)

# ------------------------------
# إدارة أوامر البوت
# ------------------------------
async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # فقط المشرفين يتفاعلون
    if not is_admin(user_id):
        return

    # تسجيل بيانات المناظرة الأولية
    if not session["active"]:
        if session["creator_id"] is None:
            session["creator_id"] = user_id
            await update.message.reply_text("تم تسجيلك كمشرف أول للمناظرة.\nأرسل عنوان المناظرة:")
            return
        elif session["debate_title"] is None:
            session["debate_title"] = text
            await update.message.reply_text(f"تم تسجيل العنوان: {text}\nأرسل اسم المحاور الأول:")
            return
        elif session["speaker1"] is None:
            session["speaker1"] = text
            await update.message.reply_text(f"تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:")
            return
        elif session["speaker2"] is None:
            session["speaker2"] = text
            await update.message.reply_text("أدخل الوقت لكل مداخلة (مثال: 3د):")
            return
        elif session["time_per_turn"] is None:
            if text.endswith("د"):
                session["time_per_turn"] = int(text[:-1]) * 60
                await update.message.reply_text(
                    f"تم تحديد الوقت: {text}\nاكتب 'ابدأ الوقت' للبدء."
                )
                return
        elif text == "ابدأ الوقت":
            session["active"] = True
            session["current_speaker"] = session["speaker1"]
            session["remaining_time"] = session["time_per_turn"]
            session["turn_start_time"] = datetime.now()
            session["timer_running"] = True
            asyncio.create_task(timer_task())
            await send_group_message(
                f"⏳ تم بدء المناظرة!\n"
                f"🎙️ مناظرة: {session['debate_title']}\n"
                f"👤 المتحدث الآن: 🟢 {session['current_speaker']}\n"
                f"⏱️ الوقت المتبقي: {format_time(session['remaining_time'])}\n"
                f"⏳ الجولة: {session['round']}"
            )
            return

    # بعد بدء الجلسة: أوامر التحكم
    if session["active"]:
        if text == "تبديل":
            await switch_speaker()
        elif text == "توقف":
            session["timer_running"] = False
            await send_group_message(
                f"⏸️ تم إيقاف المؤقت مؤقتًا.\n"
                f"⏱️ الوقت الحالي: {format_time(session['remaining_time'])}"
            )
        elif text == "استئناف":
            session["timer_running"] = True
            session["turn_start_time"] = datetime.now()
            await send_group_message(
                f"▶️ تم استئناف المؤقت.\n"
                f"المتحدث الآن: 🟢 {session['current_speaker']}\n"
                f"⏱️ الوقت الحالي: {format_time(session['remaining_time'])}"
            )
        elif text.startswith("اضف"):
            await adjust_time(text, add=True)
        elif text.startswith("انقص"):
            await adjust_time(text, add=False)
        elif text == "اعادة":
            session["remaining_time"] = session["time_per_turn"]
            session["turn_start_time"] = datetime.now()
            await send_group_message(
                f"🔁 تم إعادة وقت المداخلة.\n"
                f"المتحدث الآن: 🟢 {session['current_speaker']}\n"
                f"⏱️ الوقت: {format_time(session['remaining_time'])}"
            )
        elif text == "تنازل":
            await switch_speaker()
        elif text == "نهاية":
            await end_debate()
        else:
            # أوامر تعديل قبل البدء
            if not session["active"]:
                await handle_pre_start_edit(text, update)

# ------------------------------
# وظائف المساعدة للأوامر
# ------------------------------
async def switch_speaker():
    if session["current_speaker"] == session["speaker1"]:
        session["current_speaker"] = session["speaker2"]
    else:
        session["current_speaker"] = session["speaker1"]
    session["remaining_time"] = session["time_per_turn"]
    session["turn_start_time"] = datetime.now()
    session["round"] += 1
    await send_group_message(
        f"🔁 الدور الآن إلى: {session['current_speaker']}\n"
        f"⏱️ الوقت: {format_time(session['remaining_time'])}\n"
        f"⏳ الجولة: {session['round']}"
    )

async def adjust_time(text, add=True):
    try:
        if text.endswith("ث"):
            seconds = int(text.split()[1][:-1])
        elif text.endswith("د"):
            seconds = int(text.split()[1][:-1]) * 60
        else:
            return
        if add:
            session["remaining_time"] += seconds
        else:
            session["remaining_time"] -= seconds
        await send_group_message(
            f"⏱️ الوقت المحدث: {format_time(session['remaining_time'])}"
        )
    except:
        pass

async def end_debate():
    session["active"] = False
    await send_group_message(f"🕒 انتهاء المناظرة: {session['debate_title']}")

async def handle_pre_start_edit(text, update):
    if text.startswith("تعديل العنوان:"):
        session["debate_title"] = text.split(":",1)[1].strip()
        await update.message.reply_text(f"تم تعديل العنوان: {session['debate_title']}")
    elif text.startswith("تعديل محاور1:"):
        session["speaker1"] = text.split(":",1)[1].strip()
        await update.message.reply_text(f"تم تعديل المحاور الأول: {session['speaker1']}")
    elif text.startswith("تعديل محاور2:"):
        session["speaker2"] = text.split(":",1)[1].strip()
        await update.message.reply_text(f"تم تعديل المحاور الثاني: {session['speaker2']}")
    elif text.startswith("تعديل الوقت:"):
        t = text.split(":",1)[1].strip()
        if t.endswith("د"):
            session["time_per_turn"] = int(t[:-1]) * 60
            await update.message.reply_text(f"تم تعديل الوقت: {t}")

# ------------------------------
# مؤقت الجلسة
# ------------------------------
async def timer_task():
    while session["timer_running"]:
        await asyncio.sleep(1)
        session["remaining_time"] -= 1
        if session["remaining_time"] <= 0:
            await send_group_message(
                f"🚨 انتهى وقت المحاور!\n"
                f"👤 {session['current_speaker']} أكمل وقته المحدد ({format_time(session['time_per_turn'])})"
            )
            await switch_speaker()

# ------------------------------
# Flask route للـ Webhook
# ------------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(handle_message(update, None))
    return "ok"

# ------------------------------
# تسجيل الـ Webhook عند بدء البوت
# ------------------------------
async def set_webhook():
    await bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

asyncio.run(set_webhook())

# ------------------------------
# تشغيل Flask
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
