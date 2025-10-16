import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# المتغيرات البيئية
BOT_TOKEN = os.environ['BOT_TOKEN']
WEBHOOK_URL = os.environ['WEBHOOK_URL']
GROUP_ID = int(os.environ['GROUP_ID'])

admins = set()  # قائمة المشرفين ستُحدث تلقائيًا

# ------------------ تحديث المشرفين تلقائيًا ------------------
async def update_admins(app: Application):
    global admins
    chat_admins = await app.bot.get_chat_administrators(GROUP_ID)
    admins = {admin.user.id for admin in chat_admins}
    print("Current admins:", admins)

# ------------------ أوامر البوت ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بوت التايمر شغال ✅")

# هنا ضع الكود الخاص بإضافة/حذف/تعديل الوقت، التوقف، الاستئناف، التنازل، إعادة البوت
# مثال:
# async def stop_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     ...

# ------------------ تشغيل البوت ------------------
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    
    # تحديث المشرفين عند الإقلاع
    async def on_startup(app):
        await update_admins(app)
    app.post_init = on_startup

    # تشغيل Webhook
    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    asyncio.run(main())
