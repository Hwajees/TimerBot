import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)

# ======== المتغيرات ========
BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", 10000))

# ======== البيانات العالمية ========
is_paused = False
time_left = 0
admins = set()  # حفظ المشرفين تلقائيًا
speakers = {}   # لتتبع المتحدثين إذا أردت

# ======== الأدوات ========
def is_admin(user_id):
    return user_id in admins

# ======== الأوامر ========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text("بوت المناظرة جاهز!")

# تلقائي تسجيل المشرف
async def register_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    chat_admins = await context.bot.get_chat_administrators(GROUP_ID)
    for admin in chat_admins:
        admins.add(admin.user.id)
    await update.message.reply_text("تم تسجيل جميع المشرفين تلقائيًا ✅")

# التوقف
async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_paused
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    is_paused = True
    await update.message.reply_text("تم إيقاف المناظرة مؤقتًا ⏸️")

# الاستئناف
async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_paused
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    is_paused = False
    await update.message.reply_text("تم استئناف المناظرة ▶️")

# إضافة وقت
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

# إنقاص وقت
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

# إعادة المناظرة
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global time_left, is_paused
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    time_left = 0
    is_paused = False
    await update.message.reply_text("تم إعادة المناظرة 🔄")

# التنازل عن الدور
async def concede(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text(f"{update.effective_user.full_name} تنازل عن دوره 🏳️")

# تعديل أي محتوى (كمثال)
async def edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID or not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("تم تعديل النص 🔧")

# ======== إنشاء التطبيق ========
app = Application.builder().token(BOT_TOKEN).build()

# ======== إضافة الأوامر ========
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("register_admins", register_admins))
app.add_handler(CommandHandler("pause", pause))
app.add_handler(CommandHandler("resume", resume))
app.add_handler(CommandHandler("add_time", add_time))
app.add_handler(CommandHandler("remove_time", remove_time))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("concede", concede))
app.add_handler(CommandHandler("edit_text", edit_text))

# ======== تشغيل Webhook ========
if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )
