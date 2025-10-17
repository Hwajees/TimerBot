import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError


TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 أهلاً {user.first_name}!\n"
        "أنا بوت المؤقتات الزمنيّة، جاهز للعمل 🚀"
    )


async def update_admins(bot):
    try:
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


async def main():
    print("🚀 بدء تشغيل البوت...")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    PORT = int(os.environ.get("PORT", 8080))
    WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_URL').replace('https://', '')}/{TOKEN}"

    await app.bot.delete_webhook()
    await app.bot.set_webhook(WEBHOOK_URL)

    print(f"✅ Webhook مضبوط بنجاح على {WEBHOOK_URL}")

    await update_admins(app.bot)

    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL,
    )


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
