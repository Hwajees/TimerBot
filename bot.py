import asyncio
import random
import os
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")

# تحميل الرسائل من الملف
def load_messages():
    with open("messages.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

# تحميل قائمة الشاتات المسجلة
def load_chats():
    if not os.path.exists("chats.txt"):
        return set()
    with open("chats.txt", "r") as f:
        return set(line.strip() for line in f if line.strip())

# حفظ الشات الجديد في الملف
def save_chat(chat_id):
    chats = load_chats()
    if str(chat_id) not in chats:
        with open("chats.txt", "a") as f:
            f.write(f"{chat_id}\n")
        print(f"💾 تم حفظ شات جديد: {chat_id}")

MESSAGES = load_messages()
INTERVAL_HOURS = 4

# عند استقبال أي رسالة أو أمر
async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat(chat_id)
    await update.message.reply_text("✅ تم تسجيل هذا الشات لتلقي الرسائل التلقائية كل 4 ساعات.")

# إرسال رسالة عشوائية لكل الشاتات المسجلة
async def send_random_messages(bot: Bot):
    message = random.choice(MESSAGES)
    chats = load_chats()
    print(f"📨 إرسال الرسالة: {message} إلى {len(chats)} شات.")

    for chat_id in chats:
        try:
            await bot.send_message(chat_id=chat_id, text=message)
            await asyncio.sleep(1)  # مهلة صغيرة لتجنب الحظر
        except Exception as e:
            print(f"⚠️ فشل الإرسال إلى {chat_id}: {e}")

async def periodic_sender(bot: Bot):
    while True:
        await send_random_messages(bot)
        print(f"⌛ انتظار {INTERVAL_HOURS} ساعات...")
        await asyncio.sleep(INTERVAL_HOURS * 3600)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # أي رسالة تُرسل للبوت تسجّل الشات تلقائيًا
    app.add_handler(MessageHandler(filters.ALL, register_chat))

    bot = Bot(token=TOKEN)
    asyncio.create_task(periodic_sender(bot))

    print("🤖 البوت يعمل الآن وينتظر الرسائل...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())