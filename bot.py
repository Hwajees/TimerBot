import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# الحصول على التوكن من البيئة
TOKEN = os.getenv("BOT_TOKEN")

# دالة بدء البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 أهلاً {user.first_name}!\n"
        "أنا بوت المؤقتات الزمنيّة، جاهز للعمل 🚀"
    )

# دالة فحص المشرفين في المجموعة
async def update_admins(bot):
    """يتعرف على مشرفي المجموعات التي أُضيف إليها البوت."""
    try:
        # يمكنك تحديد مجموعة معينة بفحص ID (اختياري)
        chat_ids = os.getenv("GROUP_IDS", "")
        if not chat_ids:
            print("⚠️ لم يتم تحديد معرف المجموعة في البيئة (GROUP_IDS).")
            return
        for chat_id in chat_ids.split(","):
            chat_id = chat_id.strip()
            if not chat_id:
                continue
            admins = await bot.get_chat_administrators(chat_id)
            print(f"\n👑 المشرفون في المجموعة {chat_id}:")
            for admin in admins:
                print(f"- {admin.user.first_name} (@{admin.user.username or 'بدون اسم مستخدم'})")
    except TelegramError as e:
        print(f"حدث خطأ أثناء جلب المشرفين: {e}")

# دالة رئيسية لتشغيل البوت
async def main():
    print("🚀 بدء تشغيل البوت...")

    # إعداد التطبيق
    app = Application.builder().token(TOKEN).build()

    # إضافة الأوامر
    app.add_handler(CommandHandler("start", start))

    # تشغيل Webhook بدلاً من polling
    PORT = int(os.environ.get("PORT", 8080))
    WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_URL').replace('https://', '')}/{TOKEN}"

    await app.bot.delete_webhook()
    await app.bot.set_webhook(WEBHOOK_URL)

    print(f"✅ Webhook مضبوط بنجاح على {WEBHOOK_URL}")

    # جلب المشرفين (اختياري)
    await update_admins(app.bot)

    # تشغيل السيرفر ليستقبل التحديثات من Telegram
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL,
    )

if __name__ == "__main__":
    asyncio.run(main())
