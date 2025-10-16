import os
import asyncio
from telegram import Update, Bot, ChatMember
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]

# تخزين المشرفين
admins = set()

# تحديث قائمة المشرفين تلقائيًا
async def update_admins(bot):
    global admins
    try:
        chat_id = int(os.environ.get("GROUP_ID", 0))
        members = await bot.get_chat_administrators(chat_id)
        admins = {admin.user.id for admin in members}
        print(f"تم تحديث قائمة المشرفين: {admins}")
    except Exception as e:
        print(f"خطأ في تحديث المشرفين: {e}")

# مثال على أمر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبا! البوت يعمل الآن.")

# مثال على أمر خاص بالمشرفين
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admins:
        await update.message.reply_text("أنت مشرف، تم تنفيذ الأمر.")
    else:
        await update.message.reply_text("أنت لست مشرفاً.")

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # تحديث المشرفين عند بدء التشغيل
    await update_admins(app.bot)

    # إضافة الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admincmd", admin_command))

    # تشغيل البوت على الويب هوك
    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    asyncio.run(main())
