import os
import asyncio
from pyrogram import Client, filters
from flask import Flask
import threading

# -----------------------------
# إعدادات البوت الرسمي
# -----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))

bot = Client("debate-bot", bot_token=BOT_TOKEN)

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
async def timer_loop(message):
    while debate_data["active"] and not debate_data["paused"]:
        await asyncio.sleep(1)
        if debate_data["remaining_time"] > 0:
            debate_data["remaining_time"] -= 1
        else:
            debate_data["over_time"] += 1

        # تحديث الحالة كل 10 ثوانٍ أو عند تجاوز الوقت
        if debate_data["remaining_time"] % 10 == 0 or debate_data["over_time"] > 0:
            await send_debate_status(message)

# -----------------------------
# إرسال حالة المناظرة
# -----------------------------
async def send_debate_status(message):
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
# استقبال رسائل المجموعة
# -----------------------------
@bot.on_message(filters.chat(GROUP_ID) & filters.text)
async def handle_message(client, message):
    text = message.text.strip()
    user_id = message.from_user.id

    # استدعاء البوت
    if not debate_data["active"] and any(word in text for word in trigger_words):
        debate_data["initiator"] = user_id
        debate_data["active"] = True
        debate_data["turns_count"] = {}
        await message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    # إدخال البيانات الأولية من قبل المشرف الذي استدعى البوت
    if debate_data["active"] and user_id == debate_data["initiator"]:
        if debate_data["title"] == "":
            debate_data["title"] = text
            await message.reply_text(f"تم تسجيل عنوان المناظرة: {debate_data['title']}\nالآن أدخل اسم المحاور الأول:")
            return
        if debate_data["speaker1"] == "":
            debate_data["speaker1"] = text
            await message.reply_text(f"تم تسجيل المحاور الأول: {debate_data['speaker1']}\nالآن أدخل اسم المحاور الثاني:")
            return
        if debate_data["speaker2"] == "":
            debate_data["speaker2"] = text
            await message.reply_text(f"تم تسجيل المحاور الثاني: {debate_data['speaker2']}\nالآن أدخل الوقت لكل مداخلة بالدقائق (مثال: 3د):")
            return
        if debate_data["time_per_turn"] == 0:
            try:
                mins = int(text.replace("د",""))
                debate_data["time_per_turn"] = mins * 60
                await message.reply_text(f"تم تسجيل الوقت لكل مداخلة: {mins} دقائق\nاكتب 'ابدأ الوقت' لبدء المناظرة.")
            except:
                await message.reply_text("⚠️ يرجى إدخال الوقت بشكل صحيح (مثال: 3د)")
            return
        if text == "ابدأ الوقت":
            debate_data["current_speaker"] = debate_data["speaker1"]
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            debate_data["over_time"] = 0
            debate_data["turns_count"] = {debate_data["speaker1"]:0, debate_data["speaker2"]:0}
            debate_data["paused"] = False
            await message.reply_text("تم بدء المناظرة!")
            await send_debate_status(message)
            asyncio.create_task(timer_loop(message))
            return

# -----------------------------
# Flask لإبقاء Render مستيقظ
# -----------------------------
flask_app = Flask(__name__)
@flask_app.route("/")
def home():
    return "Debate Bot is running ✅"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# -----------------------------
# تشغيل البوت + Flask
# -----------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run()  # بوت رسمي فقط
