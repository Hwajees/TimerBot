import os
import asyncio
from datetime import timedelta
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request

# ------------------
# Environment Variables
# ------------------
BOT_TOKEN = os.environ['BOT_TOKEN']
GROUP_ID = int(os.environ['GROUP_ID'])
WEBHOOK_URL = os.environ['WEBHOOK_URL']

# ------------------
# Flask app for webhook
# ------------------
app = Flask(__name__)

# ------------------
# Global state
# ------------------
debate_data = {}
current_speaker = None
remaining_time = None
round_number = 1
current_user_id = None
is_paused = False

# ------------------
# Helper functions
# ------------------
async def send_group_message(app, text):
    await app.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode='HTML')

def format_time(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m):02}:{int(s):02}"

# ------------------
# Commands
# ------------------
async def start_debate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global debate_data, current_user_id
    user = update.effective_user
    if update.effective_chat.id != GROUP_ID:
        return
    if not update.effective_user.id in context.bot_data.get('admins', []):
        return

    if not current_user_id:
        current_user_id = user.id
        debate_data.clear()
        await update.message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global debate_data, current_user_id
    user = update.effective_user

    if update.effective_chat.id != GROUP_ID:
        return

    if not user.id in context.bot_data.get('admins', []):
        return

    text = update.message.text.strip()

    if current_user_id and user.id != current_user_id:
        # بعد التسجيل الأولي، أي مشرف يمكن استخدام الأوامر
        pass

    # تسجيل بيانات المناظرة الأولية
    if 'title' not in debate_data:
        debate_data['title'] = text
        await update.message.reply_text(f"تم تسجيل العنوان: {text}\nالآن أرسل اسم المحاور الأول:")
        return

    if 'speaker1' not in debate_data:
        debate_data['speaker1'] = text
        await update.message.reply_text(f"تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:")
        return

    if 'speaker2' not in debate_data:
        debate_data['speaker2'] = text
        await update.message.reply_text(f"تم تسجيل المحاور الثاني: {text}\nأدخل الوقت لكل مداخلة (مثال: 3د):")
        return

    if 'time' not in debate_data:
        # تحويل الوقت للنظام الداخلي
        try:
            if 'د' in text:
                minutes = int(text.replace('د',''))
                debate_data['time'] = minutes * 60
                await update.message.reply_text(f"تم تحديد الوقت: {minutes} دقيقة.\nاكتب 'ابدأ الوقت' للبدء.")
            else:
                await update.message.reply_text("استخدم الصيغة الصحيحة مثل: 5د")
        except:
            await update.message.reply_text("خطأ في إدخال الوقت، حاول مرة أخرى.")
        return

    # الأوامر أثناء المناظرة
    await handle_debate_commands(update, context)

async def handle_debate_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_speaker, remaining_time, round_number, is_paused
    text = update.message.text.strip()

    if text == 'ابدأ الوقت':
        current_speaker = 'speaker1'
        remaining_time = debate_data['time']
        await send_group_message(context.application, f"⏳ تم بدء المناظرة!\nالمتحدث الآن: 🟢 {debate_data[current_speaker]}")
        asyncio.create_task(run_timer(context.application))
        return

    # إضافة باقي أوامر تبديل، توقف، استئناف، تنازل، اضف، انقص، اعادة، نهاية
    # (سيتم تطويرها لاحقًا بالتفصيل)

async def run_timer(app):
    global remaining_time, current_speaker, round_number, is_paused
    while remaining_time > 0:
        if not is_paused:
            await asyncio.sleep(1)
            remaining_time -= 1
        # يمكن إرسال تحديث كل دقيقة أو 30 ثانية

# ------------------
# Flask webhook endpoint
# ------------------
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.create_task(app_bot.process_update(update))
    return 'ok'

# ------------------
# Main
# ------------------
app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

# إعداد قائمة المشرفين في bot_data (يمكن تحديثها حسب الحاجة)
app_bot.bot_data['admins'] = []  # ضع هنا IDs المشرفين

app_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app_bot.add_handler(CommandHandler('start', start_debate))

# تشغيل Webhook
bot = app_bot.bot
asyncio.get_event_loop().run_until_complete(bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}"))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
