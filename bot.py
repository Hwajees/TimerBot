import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROUP_ID = int(os.environ.get('GROUP_ID'))
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

# =================== Global State ===================
debate_data = {
    'title': None,
    'speaker1': None,
    'speaker2': None,
    'time_per_turn': None,
    'current_speaker': None,
    'remaining_time': None,
    'turn_start': None,
    'round': 1,
    'active': False,
    'supervisors': set(),
    'turn_count': {'speaker1':0, 'speaker2':0},
}

# =================== Helper Functions ===================
async def is_supervisor(update: Update):
    user_id = update.effective_user.id
    if not debate_data['supervisors']:
        debate_data['supervisors'].add(user_id)
        return True
    return user_id in debate_data['supervisors']

async def send_message(update: Update, text):
    await update.message.reply_text(text)

# =================== Handlers ===================
async def start_debate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_supervisor(update):
        return
    debate_data['title'] = None
    debate_data['speaker1'] = None
    debate_data['speaker2'] = None
    debate_data['time_per_turn'] = None
    debate_data['current_speaker'] = None
    debate_data['active'] = False
    await send_message(update, 'تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    if not await is_supervisor(update):
        return

    text = update.message.text.strip()

    # ============ Initial Registration ============
    if debate_data['title'] is None:
        debate_data['title'] = text
        await send_message(update, f'تم تسجيل العنوان: {text}\nالآن أرسل اسم المحاور الأول:')
        return

    if debate_data['speaker1'] is None:
        debate_data['speaker1'] = text
        await send_message(update, f'تم تسجيل المحاور الأول: {text}\nأرسل اسم المحاور الثاني:')
        return

    if debate_data['speaker2'] is None:
        debate_data['speaker2'] = text
        await send_message(update, 'أدخل الوقت لكل مداخلة (مثال: 5د):')
        return

    if debate_data['time_per_turn'] is None:
        try:
            if 'د' in text:
                debate_data['time_per_turn'] = int(text.replace('د','')) * 60
            else:
                debate_data['time_per_turn'] = int(text)
            await send_message(update, f'تم تحديد الوقت: {text} دقيقة.\nاكتب "ابدأ الوقت" للبدء.')
        except ValueError:
            await send_message(update, 'الرجاء إدخال وقت صحيح بالدقائق.')
        return

    # ============ Commands during debate ============
    if text.lower() == 'ابدأ الوقت':
        debate_data['active'] = True
        debate_data['current_speaker'] = 'speaker1'
        debate_data['remaining_time'] = debate_data['time_per_turn']
        debate_data['turn_start'] = datetime.now()
        debate_data['turn_count']['speaker1'] +=1
        await send_message(update, f'⏳ تم بدء المناظرة!\nالمتحدث الآن: 🟢 {debate_data[debate_data["current_speaker"]]}')
        return

    if not debate_data['active']:
        # ============ Editing commands before start ============
        if text.startswith('تعديل العنوان:'):
            debate_data['title'] = text.split(':',1)[1].strip()
            await send_message(update, f'تم تعديل العنوان: {debate_data["title"]}')
            return
        if text.startswith('تعديل محاور1:'):
            debate_data['speaker1'] = text.split(':',1)[1].strip()
            await send_message(update, f'تم تعديل المحاور الأول: {debate_data["speaker1"]}')
            return
        if text.startswith('تعديل محاور2:'):
            debate_data['speaker2'] = text.split(':',1)[1].strip()
            await send_message(update, f'تم تعديل المحاور الثاني: {debate_data["speaker2"]}')
            return
        if text.startswith('تعديل الوقت:'):
            debate_data['time_per_turn'] = int(text.split(':',1)[1].strip())*60
            await send_message(update, f'تم تعديل الوقت لكل مداخلة: {debate_data["time_per_turn"]//60}د')
            return

    # ============ Debate commands ============
    if text == 'تبديل':
        if debate_data['current_speaker']=='speaker1':
            debate_data['current_speaker']='speaker2'
        else:
            debate_data['current_speaker']='speaker1'
        debate_data['remaining_time'] = debate_data['time_per_turn']
        debate_data['turn_start'] = datetime.now()
        debate_data['turn_count'][debate_data['current_speaker']]+=1
        await send_message(update, f'🔁 الدور انتقل الآن إلى: {debate_data[debate_data["current_speaker"]]}')
        return

    if text == 'توقف':
        debate_data['active'] = False
        await send_message(update, f'⏸️ تم إيقاف المؤقت مؤقتًا.')
        return

    if text == 'استئناف':
        debate_data['active'] = True
        await send_message(update, f'▶️ تم استئناف المؤقت.\nالمتحدث الآن: {debate_data[debate_data["current_speaker"]]}')
        return

    if text == 'تنازل':
        if debate_data['current_speaker']=='speaker1':
            debate_data['current_speaker']='speaker2'
        else:
            debate_data['current_speaker']='speaker1'
        debate_data['remaining_time'] = debate_data['time_per_turn']
        debate_data['turn_start'] = datetime.now()
        debate_data['turn_count'][debate_data['current_speaker']]+=1
        await send_message(update, f'🙋‍♂️ المتحدث تنازل عن وقته. الدور الآن: {debate_data[debate_data["current_speaker"]]}')
        return

    if text.startswith('اضف') or text.startswith('انقص'):
        amount = 0
        if 'ث' in text:
            amount = int(text.replace('اضف','').replace('انقص','').replace('ث','').strip())
        elif 'د' in text:
            amount = int(text.replace('اضف','').replace('انقص','').replace('د','').strip())*60
        if text.startswith('اضف'):
            debate_data['remaining_time'] += amount
        else:
            debate_data['remaining_time'] = max(0, debate_data['remaining_time'] - amount)
        await send_message(update, f'⏱️ الوقت الحالي للمحاور: {debate_data["remaining_time"]//60}د {debate_data["remaining_time"]%60}ث')
        return

    if text == 'اعادة':
        debate_data['remaining_time'] = debate_data['time_per_turn']
        debate_data['turn_start'] = datetime.now()
        await send_message(update, f'🔁 تم إعادة وقت المداخلة للمحاور الحالي.')
        return

    if text == 'نهاية':
        debate_data['active'] = False
        summary = f"📊 نتائج المناظرة: {debate_data['title']}\n"
        summary += f"🟢 {debate_data['speaker1']}\n🗣️ عدد المداخلات: {debate_data['turn_count']['speaker1']}\n"
        summary += f"🔵 {debate_data['speaker2']}\n🗣️ عدد المداخلات: {debate_data['turn_count']['speaker2']}\n"
        await send_message(update, summary)
        return

# =================== Main ===================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler('start', start_debate))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
