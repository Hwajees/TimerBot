import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", 10000))

# ===== البيانات =====
is_paused = False
time_left = 0
admins = set()

# ===== الأدوات =====
async def register_admins(context: ContextTypes.DEFAULT_TYPE):
    chat_admins = await context.bot.get_chat_administrators(GROUP_ID)
    for admin in chat_admins:
        admins.add(admin.user.id)

def is_admin(user_id):
    return user_id in admins

# ===== الأوامر =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await register_admins(context)  # تسجيل المشرفين تلقائياً عند أول أمر
    await update.message.reply_text("بوت المناظرة جاهز! ✅")

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_paused
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    is_paused = True
    await update.message.reply_text("تم إيقاف المناظرة مؤقتًا ⏸️")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_paused
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    is_paused = False
    await update.message.reply_text("تم استئناف المناظرة ▶️")

async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global time_left
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    try:
        amount = int(context.args[0])
        time_left += amount
        await update.message.reply_text(f"تم إضافة {amount} ثانية ⏱️")
    except:
        await update.message.reply_text("استخدم: /add_time <عدد_الثواني>")

async def remove_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global time_left
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    try:
        amount = int(context.args[0])
        time_left -= amount
        await update.message.reply_text(f"تم إنقاص {amount} ثانية ⏱️")
    except:
        await update.message.reply_text("استخدم: /remove_time <عدد_الثواني>")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global time_left, is_paused
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    time_left = 0
    is_paused = False
    await update.message.reply_text("تم إعادة المناظرة 🔄")

async def concede(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text(f"{update.effective_user.full_name} تنازل عن دوره 🏳️")

async def edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("تم تعديل النص 🔧")

# ===== التطبيق =====
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("pause", pause))
app.add_handler(CommandHandler("resume", resume))
app.add_handler(CommandHandler("add_time", add_time))
app.add_handler(CommandHandler("remove_time", remove_time))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("concede", concede))
app.add_handler(CommandHandler("edit_text", edit_text))

# ===== تشغيل Webhook =====
if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )
