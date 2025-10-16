import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
GROUP_ID = int(os.environ.get("GROUP_ID", 0))

# تخزين المشرفين
admins = set()

async def update_admins(bot):
    global admins
    try:
        members = await bot.get_chat_administrators(GROUP_ID)
        admins = {admin.user.id for admin in members}
        print(f"تم تحديث قائمة المشرفين: {admins}")
    except Exception as e:
        print(f"خطأ في تحديث المشرفين: {e}")

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبا! البوت يعمل الآن.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admins:
        await update.message.reply_text("أنت مشرف، تم تنفيذ الأمر.")
    else:
        await update.message.reply_text("أنت لست مشرفاً.")

# بناء التطبيق
app = ApplicationBuilder().token(BOT_TOKEN).build()

# إضافة الأوامر
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admincmd", admin_command))

# تحديث المشرفين عند بدء التشغيل
app.post_init = update_admins(app.bot)

# تشغيل Webhook
app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 10000)),
    webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
)
