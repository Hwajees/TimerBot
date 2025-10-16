import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio

# ---------------- المتغيرات البيئية ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
GROUP_ID = int(os.environ.get("GROUP_ID"))

# ---------------- المتغيرات العالمية ----------------
admins = set()
paused = False
timers = {}  # لتخزين الوقت لكل مستخدم {user_id: time_in_seconds}

# ---------------- وظائف مساعدة ----------------
async def update_admins(context: ContextTypes.DEFAULT_TYPE = None):
    global admins
    chat_admins = await context.bot.get_chat_administrators(GROUP_ID)
    admins = {admin.user.id for admin in chat_admins}
    print("تم تحديث قائمة المشرفين:", admins)

def is_admin(user_id):
    return user_id in admins

# ---------------- أوامر البوت ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبًا! البوت يعمل 🔥")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "الأوامر:\n"
        "/start - تشغيل البوت\n"
        "/help - قائمة الأوامر\n"
        "/pause - إيقاف البوت\n"
        "/resume - استئناف البوت\n"
        "/addtime - إضافة وقت\n"
        "/removetime - إنقاص وقت\n"
        "/resetbot - إعادة البوت\n"
        "/transfer - التنازل عن الوقت"
    )

# ----- التوقف والاستئناف -----
async def pause_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    if is_admin(update.effective_user.id):
        paused = True
        await update.message.reply_text("تم إيقاف البوت ⏸️")
    else:
        await update.message.reply_text("فقط المشرفين يمكنهم التوقف.")

async def resume_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global paused
    if is_admin(update.effective_user.id):
        paused = False
        await update.message.reply_text("تم استئناف البوت ▶️")
    else:
        await update.message.reply_text("فقط المشرفين يمكنهم الاستئناف.")

# ----- إضافة / إنقاص الوقت -----
async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط المشرفين يمكنهم تعديل الوقت.")
        return
    try:
        user_id = int(context.args[0])
        seconds = int(context.args[1])
        timers[user_id] = timers.get(user_id, 0) + seconds
        await update.message.reply_text(f"تمت إضافة {seconds} ثانية للمستخدم {user_id}.")
    except Exception as e:
        await update.message.reply_text("الاستخدام: /addtime <user_id> <seconds>")

async def remove_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط المشرفين يمكنهم تعديل الوقت.")
        return
    try:
        user_id = int(context.args[0])
        seconds = int(context.args[1])
        timers[user_id] = max(0, timers.get(user_id, 0) - seconds)
        await update.message.reply_text(f"تمت إزالة {seconds} ثانية من المستخدم {user_id}.")
    except Exception as e:
        await update.message.reply_text("الاستخدام: /removetime <user_id> <seconds>")

# ----- إعادة البوت -----
async def reset_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط المشرفين يمكنهم إعادة البوت.")
        return
    timers.clear()
    await update.message.reply_text("تم إعادة تشغيل البوت وحذف كل الأوقات ⏰")

# ----- التنازل -----
async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from_user = update.effective_user.id
        to_user = int(context.args[0])
        seconds = int(context.args[1])
        if timers.get(from_user, 0) < seconds:
            await update.message.reply_text("ليس لديك وقت كافٍ للتنازل.")
            return
        timers[from_user] -= seconds
        timers[to_user] = timers.get(to_user, 0) + seconds
        await update.message.reply_text(f"تم التنازل عن {seconds} ثانية للمستخدم {to_user}.")
    except Exception as e:
        await update.message.reply_text("الاستخدام: /transfer <user_id> <seconds>")

# ---------------- إعداد البوت ----------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("pause", pause_bot))
app.add_handler(CommandHandler("resume", resume_bot))
app.add_handler(CommandHandler("addtime", add_time))
app.add_handler(CommandHandler("removetime", remove_time))
app.add_handler(CommandHandler("resetbot", reset_bot))
app.add_handler(CommandHandler("transfer", transfer))

# ---------------- تشغيل البوت ----------------
# تحديث قائمة المشرفين أول مرة
asyncio.create_task(update_admins(app))

# تشغيل Webhook مباشرة بدون asyncio.run()
app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 10000)),
    webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
)
