import os
import threading
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))

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
def timer_loop(context: CallbackContext):
    if debate_data["active"] and not debate_data["paused"]:
        if debate_data["remaining_time"] > 0:
            debate_data["remaining_time"] -= 1
        else:
            debate_data["over_time"] += 1
        # تحديث الرسالة كل دقيقة أو حسب الحاجة
        context.job_queue.run_once(timer_loop, 1)

# -----------------------------
# إرسال حالة المناظرة
# -----------------------------
def send_debate_status(context: CallbackContext):
    chat_id = GROUP_ID
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
    context.bot.send_message(chat_id=chat_id, text=msg)

# -----------------------------
# استقبال رسائل المجموعة
# -----------------------------
def handle_message(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    user_id = update.message.from_user.id

    # استدعاء البوت
    if not debate_data["active"] and any(word in text for word in trigger_words):
        debate_data["initiator"] = user_id
        debate_data["active"] = True
        debate_data["turns_count"] = {}
        update.message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    # إدخال البيانات الأولية
    if debate_data["active"] and user_id == debate_data["initiator"]:
        if debate_data["title"] == "":
            debate_data["title"] = text
            update.message.reply_text(f"تم تسجيل عنوان المناظرة: {debate_data['title']}\nالآن أدخل اسم المحاور الأول:")
            return
        if debate_data["speaker1"] == "":
            debate_data["speaker1"] = text
            update.message.reply_text(f"تم تسجيل المحاور الأول: {debate_data['speaker1']}\nالآن أدخل اسم المحاور الثاني:")
            return
        if debate_data["speaker2"] == "":
            debate_data["speaker2"] = text
            update.message.reply_text(f"تم تسجيل المحاور الثاني: {debate_data['speaker2']}\nالآن أدخل الوقت لكل مداخلة بالدقائق (مثال: 3د):")
            return
        if debate_data["time_per_turn"] == 0:
            try:
                mins = int(text.replace("د",""))
                debate_data["time_per_turn"] = mins * 60
                update.message.reply_text(f"تم تسجيل الوقت لكل مداخلة: {mins} دقائق\nاكتب 'ابدأ الوقت' لبدء المناظرة.")
            except:
                update.message.reply_text("⚠️ يرجى إدخال الوقت بشكل صحيح (مثال: 3د)")
            return
        if text == "ابدأ الوقت":
            debate_data["current_speaker"] = debate_data["speaker1"]
            debate_data["remaining_time"] = debate_data["time_per_turn"]
            debate_data["over_time"] = 0
            debate_data["turns_count"] = {debate_data["speaker1"]:0, debate_data["speaker2"]:0}
            debate_data["paused"] = False
            update.message.reply_text("تم بدء المناظرة!")
            send_debate_status(context)
            context.job_queue.run_once(timer_loop, 1)
            return

# -----------------------------
# Flask لإبقاء Render مستيقظ
# -----------------------------
from flask import Flask
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
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & Filters.chat(GROUP_ID), handle_message))

    threading.Thread(target=run_flask).start()
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
