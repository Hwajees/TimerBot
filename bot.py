import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ===== المتغيرات =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # ضع توكن البوت هنا أو في environment
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # إذا أردت webhooks

admins = set()  # لتخزين معرفات المشرفين
timers = {}     # لتخزين بيانات الوقت لكل مستخدم/محادثة

# ===== دوال الأوامر =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! البوت جاهز للعمل.")

async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إضافة الوقت!")  # ضع منطقك هنا

async def sub_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم نقص الوقت!")  # ضع منطقك هنا

async def pause_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إيقاف البوت مؤقتًا!")  # ضع منطقك هنا

async def resume_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم استئناف البوت!")  # ضع منطقك هنا

async def resign_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم التنازل عن المشرفية!")  # ضع منطقك هنا

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جارٍ إعادة تشغيل البوت...")  # ضع منطقك هنا

# ===== تحديث قائمة المشرفين تلقائيًا =====
async def update_admins(bot):
    global all_admins
    all_admins = set()

    for update in updates:
        chat = update.effective_chat
        if chat:
            admins = await bot.get_chat_administrators(chat.id)
            admin_ids = [admin.user.id for admin in admins]
            all_admins.update(admin_ids)

    print(f"تم تحديث قائمة المشرفين: {all_admins}")

# ===== دوال المساعدة =====
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("الأمر غير معروف.")

# ===== إعداد البوت =====
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtime", add_time))
    app.add_handler(CommandHandler("subtime", sub_time))
    app.add_handler(CommandHandler("pause", pause_timer))
    app.add_handler(CommandHandler("resume", resume_timer))
    app.add_handler(CommandHandler("resign", resign_admin))
    app.add_handler(CommandHandler("restart", restart_bot))

    # أي أوامر غير معروفة
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # تحديث قائمة المشرفين عند بدء البوت
    await update_admins(app.bot)

    # تشغيل البوت على polling داخل المحادثة الخاصة
    await app.start()
    await app.updater.start_polling()
    print("البوت جاهز للعمل في المحادثة الخاصة.")
    await asyncio.Event().wait()  # إبقاء البوت يعمل

if __name__ == "__main__":
    asyncio.run(main())
