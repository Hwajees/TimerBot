import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ----------------------
# إعداد اللوج
# ----------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------------
# المتغيرات البيئية
# ----------------------
BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]

# ----------------------
# قائمة المشرفين (ستتحدث تلقائيًا)
# ----------------------
admins = set()

async def update_admins(app: Application):
    """تحديث قائمة المشرفين تلقائيًا"""
    global admins
    chat_admins = await app.bot.get_chat_administrators(GROUP_ID)
    admins = {admin.user.id for admin in chat_admins}

# ----------------------
# أوامر البوت
# ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بوت الوقت فعال ✅")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in admins:
        await update.message.reply_text("تم التوقف مؤقتًا ⏸️")
        # هنا ضع الكود الخاص بالتوقف
    else:
        await update.message.reply_text("أنت لست مشرفًا ❌")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in admins:
        await update.message.reply_text("تم الاستئناف ▶️")
        # هنا ضع الكود الخاص بالاستئناف
    else:
        await update.message.reply_text("أنت لست مشرفًا ❌")

async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in admins:
        await update.message.reply_text("تم إضافة الوقت ⏱️")
        # هنا ضع الكود الخاص بالإضافة
    else:
        await update.message.reply_text("أنت لست مشرفًا ❌")

async def remove_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in admins:
        await update.message.reply_text("تم إنقاص الوقت ⏱️")
        # هنا ضع الكود الخاص بالنقصان
    else:
        await update.message.reply_text("أنت لست مشرفًا ❌")

async def relinquish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in admins:
        await update.message.reply_text("تم التنازل ⚡")
        # هنا ضع الكود الخاص بالتنازل
    else:
        await update.message.reply_text("أنت لست مشرفًا ❌")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in admins:
        await update.message.reply_text("تم إعادة ضبط البوت 🔄")
        # هنا ضع الكود الخاص بإعادة البوت
    else:
        await update.message.reply_text("أنت لست مشرفًا ❌")

# ----------------------
# تشغيل البوت على Webhook
# ----------------------
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # تحديث المشرفين تلقائيًا
    await update_admins(app)

    # إضافة Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("addtime", add_time))
    app.add_handler(CommandHandler("removetime", remove_time))
    app.add_handler(CommandHandler("relinquish", relinquish))
    app.add_handler(CommandHandler("reset", reset))

    # تشغيل الـ webhook
    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
