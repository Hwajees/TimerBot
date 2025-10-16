import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask
import threading

# -----------------------------
# إعدادات البوت
# -----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))

app = Client("debate-bot", bot_token=BOT_TOKEN)

# -----------------------------
# حالة المناظرة
# -----------------------------
debate_data = {
    "active": False,
    "initiator": None,
    "title": "",
    "speaker1": "",
    "speaker2": "",
    "time_per_turn": 0,
    "current_speaker": "",
    "remaining_time": 0,
    "round": 1,
    "turns_count": {},
    "over_time": 0,
    "paused": False
}

trigger_words = ["بوت المؤقت","المؤقت","بوت الساعة","بوت الساعه","الساعة","الساعه"]

# -----------------------------
# عداد الوقت
# -----------------------------
async def timer_loop(chat_id: int):
    while debate_data["active"] and not debate_data["paused"]:
        await asyncio.sleep(1)
        if debate_data["remaining_time"] > 0:
            debate_data["remaining_time"] -= 1
        else:
            debate_data["over_time"] += 1
        # إرسال رسالة كل دقيقة أو عند انتهاء الوقت يمكن إضافتها حسب الحاجة

# -----------------------------
# إرسال حالة المناظرة
# -----------------------------
async def send_debate_status(message: Message):
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
    await message.reply_text(msg)

# -----------------------------
# استقبال الرسائل
# -----------------------------
@app.on_message(filters.chat(GROUP_ID) & filters.text)
async def handle_message(client: Client, message: Message):
    global debate_data
    text = message.text.strip()
    user_id = message.from_user.id

    # -----------------------------
    # استدعاء البوت
    # -----------------------------
    if not debate_data["active"] and any(word in text for word in trigger_words):
        debate_data["initiator"] = user_id
        debate_data["active"] = True
        debate_data["turns_count"] = {}
        await message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    # -----------------------------
    # إدخال البيانات الأولية
    # -----------------------------
    if debate_data["active"] and user_id == debate_data["initiator"]:
        # تعديل العنوان
        if debate_data["title"] == "":
            if text.lower().startswith("تعديل العنوان:"):
                debate_data["title"] = text.split(":",1)[1].strip()
                await message.reply_text(f"تم تعديل العنوان: {debate_data['title']}")
            else:
                debate_data["title"] = text
                await message.reply_text(f"تم تسجيل عنوان المناظرة: {debate_data['title']}\nالآن أدخل اسم المحاور الأول:")
            return
        # المحاور الأول
        if debate_data["speaker1"] == "":
            if text.lower().startswith("تعديل محاور1:"):
                debate_data["speaker1"] = text.split(":",1)[1].strip()
                await message.reply_text(f"تم تعديل اسم المحاور الأول: {debate_data['speaker1']}")
            else:
                debate_data["speaker1"] = text
                await message.reply_text(f"تم تسجيل المحاور الأول: {debate_data['speaker1']}\nالآن أدخل اسم المحاور الثاني:")
            return
        # المحاور الثاني
        if debate_data["speaker2"] == "":
            if text.lower().startswith("تعديل محاور2:"):
                debate_data["speaker2"] = text.split(":",1)[1].strip()
                await message.reply_text(f"تم تعديل اسم المحاور الثاني: {debate_data['speaker2']}")
            else:
                debate_data["speaker2"] = text
                await message.reply_text(f"تم تسجيل المحاور الثاني: {debate_data['speaker2']}\nالآن أدخل الوقت لكل مداخلة بالدقائق:")
            return
        # الوقت
        if debate_data["time_per_turn"] == 0:
            if text.lower().startswith("تعديل الوقت:"):
                mins = int(text.split(":",1)[1].replace("د","").strip())
                debate_data["time_per_turn"] = mins * 60
                await message.reply_text(f"تم تعديل الوقت لكل مداخلة: {mins} دقائق\nاكتب 'ابدأ الوقت' لبدء المناظرة.")
            else:
                mins = int(text.replace("د","").strip())
                debate_data["time_per_turn"] = mins * 60
                await message.reply_text(f"تم تسجيل الوقت لكل مداخلة: {mins} دقائق\nاكتب 'ابدأ الوقت' لبدء المناظرة.")
            return
        # بدء المناظرة
        if text == "ابدأ الوقت":
            debate_data["current_speaker"] = debate_data["speaker1"]
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            debate_data["over_time"] = 0
            debate_data["turns_count"] = {debate_data["speaker1"]:0, debate_data["speaker2"]:0}
            debate_data["paused"] = False
            await message.reply_text("تم بدء المناظرة!")
            await send_debate_status(message)
            asyncio.create_task(timer_loop(message.chat.id))
            return

    # -----------------------------
    # أوامر بعد بدء المناظرة
    # -----------------------------
    if debate_data["current_speaker"] != "":
        # هنا نضيف كل أوامر: تبديل، توقف، استئناف، تنازل، اعادة، نهاية، اضف/انقص
        # هذا جزء طويل ويمكن نقله مباشرة من كود python-telegram-bot السابق مع تعديل client
        # سأكتب لك باقي الأوامر إذا أردت الآن
        pass

# -----------------------------
# Flask لإبقاء Render مستيقظ
# -----------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Debate Bot is running ✅"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# -----------------------------
# تشغيل البوت + Flask
# -----------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run()
