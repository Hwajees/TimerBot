import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ----------------------------
# المتغيرات البيئية
# ----------------------------
BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])  # مثال: -1003119659803
WEBHOOK_URL = os.environ["WEBHOOK_URL"]

# ----------------------------
# قائمة المشرفين
# ----------------------------
admins = set()

# ----------------------------
# تحديث المشرفين تلقائيًا
# ----------------------------
async def update_admins(bot):
    global admins
    try:
        members = await bot.get_chat_administrators(GROUP_ID)
        admins = {admin.user.id for admin in members}
        print(f"تم تحديث قائمة المشرفين: {admins}")
    except Exception as e:
        print(f"خطأ في تحديث المشرفين: {e}")

def post_init_wrapper(app):
    # تشغيل الكوروتين دون انتظار (fire-and-forget)
    asyncio.create_task(update_admins(app.bot))

# ----------------------------
# أوامر البوت
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! البوت يعمل الآن.")

async def stop_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        await update.message.reply_text("أنت لست مشرفاً.")
        return
    # هنا ضع الكود الخاص بإيقاف البوت
    await update.message.reply_text("تم إيقاف البوت مؤقتاً.")

async def resume_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        await update.message.reply_text("أنت لست مشرفاً.")
        return
    # هنا ضع الكود الخاص باستئناف البوت
    await update.message.reply_text("تم استئناف البوت.")

async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        await update.message.reply_text("أنت لست مشرفاً.")
        return
    # هنا ضع الكود الخاص بإضافة الوقت
    await update.message.reply_text("تم إضافة الوقت.")

async def remove_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        await update.message.reply_text("أنت لست مشرفاً.")
        return
    # هنا ضع الكود الخاص بحذف الوقت
    await update.message.reply_text("تم إزالة الوقت.")

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        await update.message.reply_text("أنت لست مشرفاً.")
        return
    # هنا ضع الكود الخاص بالتنازل
    await update.message.reply_text("تم التنازل.")

async def reset_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        await update.message.reply_text("أنت لست مشرفاً.")
        return
    # هنا ضع الكود الخاص بإعادة البوت
    await update.message.reply_text("تم إعادة البوت.")

# ----------------------------
# التطبيق الرئيسي
# ----------------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # تعيين post_init لتحديث المشرفين
    app.post_init = post_init_wrapper

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_timer))
    app.add_handler(CommandHandler("resume", resume_timer))
    app.add_handler(CommandHandler("addtime", add_time))
    app.add_handler(CommandHandler("removetime", remove_time))
    app.add_handler(CommandHandler("transfer", transfer))
    app.add_handler(CommandHandler("reset", reset_bot))

    # يمكنك إضافة المزيد من MessageHandler إذا لزم الأمر

    # تشغيل Webhook
    port = int(os.environ.get("PORT", 10000))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
