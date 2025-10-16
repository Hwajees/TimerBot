import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ------------------------------
# المتغيرات
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://timerbot-fjtl.onrender.com")
PORT = int(os.environ.get("PORT", 10000))
GROUP_ID = int(os.environ.get("GROUP_ID", -1001234567890))  # ضع هنا معرف مجموعتك إذا أردت

admins = set()  # ستُخزن هنا قائمة المشرفين تلقائيًا
# ------------------------------

# --- دوال البوت ---

async def update_admins(bot):
    global admins
    try:
        members = await bot.get_chat_administrators(GROUP_ID)
        admins = {admin.user.id for admin in members}
        print(f"تم تحديث قائمة المشرفين: {admins}")
    except Exception as e:
        print(f"خطأ في تحديث المشرفين: {e}")

async def post_init(app: Application):
    await update_admins(app.bot)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبًا! البوت جاهز للعمل ✅")

# مثال لأمر عام
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

# --- هنا ضع باقي أوامر البوت: تعديل، توقف، استئناف، إضافة/حذف وقت، إعادة البوت ---
# يمكنك إنشاء دوال async لكل أمر، والتحقق من كون المستخدم ضمن admins قبل تنفيذ أي إجراء

# ------------------------------
# إعداد التطبيق
app = Application.builder().token(BOT_TOKEN).build()
app.post_init = post_init

# --- تسجيل الأوامر ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ping", ping))

# --- لتسجيل رسائل نصية عامة ---
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))

# ------------------------------
# تشغيل Webhook
if __name__ == "__main__":
    app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 10000)),
    webhook_url=f"{WEBHOOK_URL}",  # بدون /BOT_TOKEN
)
