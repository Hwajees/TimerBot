import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask
import threading

# -----------------------------
# إعدادات البوت الرسمي
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
async def timer_loop(message: Message):
    while debate_data["active"] and not debate_data["paused"]:
        await asyncio.sleep(1)
        if debate_data["remaining_time"] > 0:
            debate_data["remaining_time"] -= 1
        else:
            debate_data["over_time"] += 1

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
# استقبال الرسائل في المجموعة
# -----------------------------
@app.on_message(filters.chat(GROUP_ID) & filters.text)
async def handle_message(client: Client, message: Message):
    global debate_data
    text = message.text.strip()
    user_id = message.from_user.id

    # استدعاء البوت
    if not debate_data["active"] and any(word in text for word in trigger_words):
        debate_data["initiator"] = user_id
        debate_data["active"] = True
        debate_data["turns_count"] = {}
        await message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    # إدخال البيانات الأولية
    if debate_data["active"] and user_id == debate_data["initiator"]:
        # إدخال أو تعديل العنوان
        if debate_data["title"] == "":
            debate_data["title"] = text
            await message.reply_text(f"تم تسجيل عنوان المناظرة: {debate_data['title']}\nالآن أدخل اسم المحاور الأول:")
            return
        # المحاور الأول
        if debate_data["speaker1"] == "":
            debate_data["speaker1"] = text
            await message.reply_text(f"تم تسجيل المحاور الأول: {debate_data['speaker1']}\nالآن أدخل اسم المحاور الثاني:")
            return
        # المحاور الثاني
        if debate_data["speaker2"] == "":
            debate_data["speaker2"] = text
            await message.reply_text(f"تم تسجيل المحاور الثاني: {debate_data['speaker2']}\nالآن أدخل الوقت لكل مداخلة بالدقائق:")
            return
        # الوقت لكل مداخلة
        if debate_data["time_per_turn"] == 0:
            try:
                mins = int(text.replace("د",""))
                debate_data["time_per_turn"] = mins * 60
                await message.reply_text(f"تم تسجيل الوقت لكل مداخلة: {mins} دقائق\nاكتب 'ابدأ الوقت' لبدء المناظرة.")
            except:
                await message.reply_text("⚠️ يرجى إدخال الوقت بشكل صحيح (مثال: 3د)")
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
            asyncio.create_task(timer_loop(message))
            return

    # أوامر بعد بدء المناظرة
    if debate_data["current_speaker"] != "":
        # تبديل المتحدث
        if text == "تبديل":
            debate_data["round"] += 1
            debate_data["over_time"] = 0
            debate_data["turns_count"][debate_data["current_speaker"]] += 1
            debate_data["current_speaker"] = debate_data["speaker2"] if debate_data["current_speaker"] == debate_data["speaker1"] else debate_data["speaker1"]
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            await send_debate_status(message)
            return

        # إيقاف مؤقت
        if text == "توقف":
            debate_data["paused"] = True
            await message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت الحالي: {debate_data['remaining_time']//60:02d}:{debate_data['remaining_time']%60:02d}")
            return

        # استئناف
        if text == "استئناف":
            debate_data["paused"] = False
            asyncio.create_task(timer_loop(message))
            await message.reply_text(f"▶️ تم استئناف المؤقت.\nالمتحدث الآن: {debate_data['current_speaker']}")
            return

        # إعادة وقت المداخلة
        if text == "اعادة":
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            debate_data["over_time"] = 0
            await message.reply_text(f"🔄 تم إعادة وقت المداخلة من البداية.\nالمتحدث الآن: {debate_data['current_speaker']}")
            return

        # إضافة أو إنقاص الوقت
        if text.startswith("اضف") or text.startswith("انقص"):
            action = "اضف" if text.startswith("اضف") else "انقص"
            try:
                num = int(''.join(filter(str.isdigit, text)))
                if "ث" in text:
                    secs = num
                elif "د" in text:
                    secs = num*60
                else:
                    await message.reply_text("⚠️ صيغة غير صحيحة! استخدم ث للثواني أو د للدقائق.")
                    return
                if action=="اضف":
                    debate_data["remaining_time"] += secs
                else:
                    debate_data["remaining_time"] -= secs
                    if debate_data["remaining_time"] < 0:
                        debate_data["over_time"] += abs(debate_data["remaining_time"])
                        debate_data["remaining_time"]=0
                await message.reply_text(f"⏱️ تم {action} الوقت. الوقت الحالي للمتحدث: {debate_data['remaining_time']//60:02d}:{debate_data['remaining_time']%60:02d}")
            except:
                await message.reply_text("⚠️ صيغة غير صحيحة! استخدم مثل: اضف ٣٠ث أو انقص ٢د")
            return

        # نهاية المناظرة
        if text == "نهاية":
            msg = f"📊 نتائج المناظرة: {debate_data['title']}\n\n"
            for speaker in [debate_data["speaker1"], debate_data["speaker2"]]:
                turns = debate_data["turns_count"].get(speaker,0)
                used_time = (turns * debate_data["time_per_turn"] + (debate_data["time_per_turn"] - debate_data["remaining_time"]))
                minutes = int(used_time // 60)
                seconds = int(used_time % 60)
                msg += f"{'🟢' if speaker == debate_data['speaker1'] else '🔵'} {speaker}\n"
                msg += f"🗣️ عدد المداخلات: {turns}\n"
                msg += f"⏱️ الوقت المستخدم: {minutes:02d}:{seconds:02d} دقيقة\n\n"
            total_time = sum([turns*debate_data["time_per_turn"] for turns in debate_data["turns_count"].values()])
            msg += f"🕒 الوقت الكلي: {int(total_time//60):02d}:{int(total_time%60):02d} دقيقة\n━━━━━━━━━━━━━━━━━━"
            await message.reply_text(msg)

            # إعادة الحالة للانتظار بعد انتهاء المناظرة
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
            await message.reply_text("✅ تم إنهاء المناظرة. البوت جاهز للمناظرة التالية.")
            return

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
