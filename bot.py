# bot.py
import os
import re
import asyncio
from datetime import timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from typing import Dict, Any

# ---------------------
# إعداد المتغيرات
# ---------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
PORT = int(os.getenv("PORT", 10000))

# ---------------------
# إعداد Flask للحفاظ على الخدمة في Render
# ---------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Debate Timer Bot is running ✅"

# ---------------------
# بيانات كل مناظرة حسب chat_id
# ---------------------
debates: Dict[int, Dict[str, Any]] = {}

# ---------------------
# كلمات الاستدعاء
# ---------------------
TRIGGERS = {"بوت المؤقت","المؤقت","بوت الساعة","بوت الساعه","الساعة","الساعه"}

# ---------------------
# مساعدة: تحويل أرقام عربية-هندية إلى لاتينية
# يدعم الأرقام: ٠١٢٣٤٥٦٧٨٩ و 0123456789
# ---------------------
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def to_latin_digits(s: str) -> str:
    return s.translate(ARABIC_DIGITS)

# ---------------------
# مساعدة: تفريغ صيغة الوقت (مثل "٣٠ث" أو "30ث" أو "2د")
# يُعيد عدد الثواني أو None
# ---------------------
def parse_time_delta(text: str):
    text = to_latin_digits(text.strip().replace(" ", ""))
    # أمثلة: 30ث 15ث 2د ٣د
    m = re.match(r"^(\d+)\s*(ث|ثانية|ثواني)$", text)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)\s*(د|دقيقة|دقائق)$", text)
    if m:
        return int(m.group(1)) * 60
    # قد يكون فقط رقم بالدقائق مثل "5" -> دقائق
    m = re.match(r"^(\d+)$", text)
    if m:
        return int(m.group(1)) * 60
    return None

# ---------------------
# تنسيق وقت hh:mm:ss أو mm:ss حسب الحاجة
# ---------------------
def fmt_hms(seconds: int) -> str:
    if seconds < 0:
        seconds = abs(seconds)
    return str(timedelta(seconds=seconds))

# ---------------------
# تحقق من أن المستخدم مشرف في الجروب
# ---------------------
async def is_admin(chat_id: int, user_id: int, app) -> bool:
    try:
        admins = await app.bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except:
        return False

# ---------------------
# إنشاء رسالة الحالة بالتنسيق المتفق عليه
# ---------------------
def build_status_text(data: Dict[str, Any]) -> str:
    title = data["title"]
    s1 = data["speaker1"]
    s2 = data["speaker2"]
    current = data["current_speaker"]
    remaining = max(0, data["remaining"])
    overtime = data["overtime"]
    rnd = data["round"]

    text = "━━━━━━━━━━━━━━━━━━\n"
    text += f"🎙️ مناظرة: {title}\n\n"
    # تعيين إيموجي
    emoji = "🟢" if current == s1 else "🔵"
    text += f"👤 المتحدث الآن: {emoji} {current}\n"
    # عرض الوقت بصيغة mm:ss أو hh:mm:ss
    mmss = fmt_hms(remaining)
    text += f"⏱️ الوقت المتبقي: {mmss}\n"
    if overtime > 0:
        ot = fmt_hms(overtime)
        text += f"🔴 تجاوز الوقت: +{ot}\n"
    text += f"⏳ الجولة: {rnd}\n"
    text += "━━━━━━━━━━━━━━━━━━"
    return text

# ---------------------
# مهمة عدّاد لكل محادثة (تعمل في الخلفية)
# تقوم بتقليل remaining كل ثانية، وتزيد overtime بعد انتهاء الوقت
# عند انتهاء الوقت ترسل رسالة نهائية وتضع الدور للمتحدث التالي (حسب "تنازل" أو "تبديل")
# ---------------------
async def run_timer(chat_id: int, app):
    data = debates.get(chat_id)
    if not data:
        return

    # كل ثانية تحديث
    while data and data["active"]:
        await asyncio.sleep(1)
        if data["paused"]:
            continue
        # نقص ثانية
        data["remaining"] -= 1
        if data["remaining"] >= 0:
            # حدث تحديث مرئي كل 5 ثوانٍ تقريبًا لتخفيف الرسائل أو حسب الحاجة
            if data["last_update_counter"] % 5 == 0:
                try:
                    await app.bot.send_message(chat_id=chat_id, text=build_status_text(data))
                except:
                    pass
            data["last_update_counter"] += 1
            continue
        # هنا remaining < 0 => بدأ تجاوز الوقت
        data["overtime"] = abs(data["remaining"])
        # نرسل حالة تجاوز الوقت
        try:
            await app.bot.send_message(chat_id=chat_id, text=build_status_text(data))
        except:
            pass
        # لا نوقف العمل تلقائيًا؛ ننتظر أمر تبديل/تنازل/نهاية من المشرف
        # لكن نرسل تنبيه مرئي مرة واحدة عند الوصول لأول مرة لتجاوز الوقت
        if not data.get("overtime_alert_sent"):
            try:
                await app.bot.send_message(chat_id=chat_id,
                    text=(f"🚨 انتهى وقت المحاور!\n"
                          f"👤 {data['current_speaker']} أكمل وقته المحدد ({fmt_hms(data['duration'])})\n"
                          f"🔁 الدور ينتقل الآن إلى: {data['alt_speaker']()}"))
            except:
                pass
            data["overtime_alert_sent"] = True
        # استمر بالعد لاحتساب تجاوز الوقت في الحقل overtime
        # (لنقم بالتحديث كل ثانية لكن بدون تبديل تلقائي)
        # loop يستمر حتى يأتي أمر تبديل/تنازل/استئناف/اعادة/نهاية
    # انتهاء الحلقة
    return

# ---------------------
# دوال مساعدة داخل data
# ---------------------
def ensure_alt_speaker_fn(data):
    # يضيف دالة الحصول على المتحدث الآخر
    def alt():
        return data["speaker2"] if data["current_speaker"] == data["speaker1"] else data["speaker1"]
    data["alt_speaker"] = alt

# ---------------------
# دالة لتجهيز مناظرة جديدة
# ---------------------
def create_new_debate(chat_id: int, initiator_id: int):
    debates[chat_id] = {
        "initiator": initiator_id,
        "active": True,       # معناها: في طور التسجيل أو قيد التشغيل
        "stage": "title",     # title -> speaker1 -> speaker2 -> duration -> ready -> running
        "title": "",
        "speaker1": "",
        "speaker2": "",
        "duration": 0,        # مدة المداخلة بالثواني
        "remaining": 0,
        "overtime": 0,
        "paused": False,
        "current_speaker": "",
        "round": 1,
        "turns": { },         # عدّ المداخلات لكل متحدث
        "last_update_counter": 0,
        "overtime_alert_sent": False
    }
    ensure_alt_speaker_fn(debates[chat_id])

# ---------------------
# دالة مساعدة لإرسال رسالة خطأ/تنبيه بصيغة موحدة
# ---------------------
async def send_notice(chat_id: int, app, text: str):
    try:
        await app.bot.send_message(chat_id=chat_id, text=text)
    except:
        pass

# ---------------------
# المعالج الرئيسي للنصوص (يعمل على الرسائل النصية داخل الجروب)
# ---------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = message.text.strip()

    # نتعامل فقط مع المجموعة المحددة
    if chat_id != GROUP_ID:
        return

    # تحقق مشرف
    if not await is_admin(chat_id, user.id, context.application):
        return  # تجاهل الاعضاء العاديين تمامًا

    # إذا استدعاء البوت لبدء التسجيل (أي مشرف يقدر يبدأ)
    if any(trigger in text for trigger in TRIGGERS):
        # لو في مناظرة شغالة بنفس الشات نعلم المشرف
        if chat_id in debates and debates[chat_id]["active"] and debates[chat_id]["stage"] != "finished":
            await message.reply_text("❗ توجد مناظرة سارية. إذا أردت إعادة بدء، اكتب 'نهاية' أولًا.")
            return
        create_new_debate(chat_id, user.id)
        await message.reply_text("تم استدعاء البوت! من فضلك أدخل عنوان المناظرة:")
        return

    # إذا لا توجد مناظرة نشطة تجاهل
    if chat_id not in debates or not debates[chat_id]["active"]:
        return

    data = debates[chat_id]

    # خلال التسجيل: فقط المشرف الذي استدعى البوت يتفاعل (المشرف الأول)
    if data["stage"] in {"title","speaker1","speaker2","duration"}:
        if user.id != data["initiator"]:
            await message.reply_text("⛔ أثناء التسجيل يتفاعل البوت مع المشرف الذي استدعى البوت فقط.")
            return
        # العنوان
        if data["stage"] == "title":
            data["title"] = text
            data["stage"] = "speaker1"
            await message.reply_text(f"تم تسجيل العنوان: {data['title']}\nالآن أرسل اسم المحاور الأول:")
            return
        # المحاور الأول
        if data["stage"] == "speaker1":
            data["speaker1"] = text
            data["stage"] = "speaker2"
            await message.reply_text(f"تم تسجيل المحاور الأول: {data['speaker1']}\nالآن أرسل اسم المحاور الثاني:")
            return
        # المحاور الثاني
        if data["stage"] == "speaker2":
            data["speaker2"] = text
            data["stage"] = "duration"
            await message.reply_text(f"تم تسجيل المحاور الثاني: {data['speaker2']}\nالآن أدخل الوقت لكل مداخلة (مثال: 5د):")
            return
        # الوقت لكل مداخلة
        if data["stage"] == "duration":
            secs = parse_time_delta(text)
            if secs is None or secs <= 0:
                await message.reply_text("⚠️ الرجاء إدخال الوقت بصيغة صحيحة مثل: 5د أو ٣د")
                return
            data["duration"] = secs
            data["remaining"] = secs
            data["current_speaker"] = data["speaker1"]
            data["turns"] = {data["speaker1"]:0, data["speaker2"]:0}
            data["stage"] = "ready"
            await message.reply_text(
                ("🎙️ مناظرة: " + data["title"] + "\n" +
                 f"👤 المحاورون: 🟢 {data['speaker1']}, 🔵 {data['speaker2']}\n" +
                 f"⏱️ الوقت لكل مداخلة: {fmt_hms(data['duration'])}\n" +
                 "اكتب 'ابدأ الوقت' للبدء.")
            )
            return

    # بعد الانتهاء من التسجيل (Stage = ready or running) => أوامر الإدارة المتفق عليها
    # يسمح لأي مشرف بإدارة الجلسة الآن
    cmd = text.strip()

    # -- أوامر التعديل أثناء التسجيل (قبل البدء): صيغة محددة --
    # تعديل العنوان: <العنوان الجديد>
    if cmd.startswith("تعديل العنوان:") and data["stage"] in {"title","speaker1","speaker2","duration","ready"}:
        # يجب أن يكون المشرف الحالي هو الذي استدعى البوت (أو أي مشرف إذا قررت خلاف ذلك)
        if user.id != data["initiator"]:
            await message.reply_text("⛔ تعديل بيانات التسجيل متاح للمشرف الذي بدأ التسجيل فقط.")
            return
        new = cmd.split("تعديل العنوان:",1)[1].strip()
        if not new:
            await message.reply_text("⚠️ الصيغة خاطئة. استخدم: تعديل العنوان: <العنوان الجديد>")
            return
        data["title"] = new
        await message.reply_text(f"✏️ تم تعديل العنوان إلى: {data['title']}")
        return

    # تعديل محاور1: <الاسم الجديد>
    if cmd.startswith("تعديل محاور1:") and data["stage"] != "running":
        if user.id != data["initiator"]:
            await message.reply_text("⛔ تعديل بيانات التسجيل متاح للمشرف الذي بدأ التسجيل فقط.")
            return
        new = cmd.split("تعديل محاور1:",1)[1].strip()
        if not new:
            await message.reply_text("⚠️ الصيغة خاطئة. استخدم: تعديل محاور1: <الاسم الجديد>")
            return
        data["speaker1"] = new
        await message.reply_text(f"✏️ تم تعديل المحاور الأول إلى: {data['speaker1']}")
        return

    # تعديل محاور2: <الاسم الجديد>
    if cmd.startswith("تعديل محاور2:") and data["stage"] != "running":
        if user.id != data["initiator"]:
            await message.reply_text("⛔ تعديل بيانات التسجيل متاح للمشرف الذي بدأ التسجيل فقط.")
            return
        new = cmd.split("تعديل محاور2:",1)[1].strip()
        if not new:
            await message.reply_text("⚠️ الصيغة خاطئة. استخدم: تعديل محاور2: <الاسم الجديد>")
            return
        data["speaker2"] = new
        await message.reply_text(f"✏️ تم تعديل المحاور الثاني إلى: {data['speaker2']}")
        return

    # تعديل الوقت: 7د (قبل البدء فقط)
    if cmd.startswith("تعديل الوقت:") and data["stage"] != "running":
        if user.id != data["initiator"]:
            await message.reply_text("⛔ تعديل بيانات التسجيل متاح للمشرف الذي بدأ التسجيل فقط.")
            return
        new = cmd.split("تعديل الوقت:",1)[1].strip()
        secs = parse_time_delta(new)
        if secs is None:
            await message.reply_text("⚠️ صيغة غير صحيحة. مثال: تعديل الوقت: 7د")
            return
        data["duration"] = secs
        data["remaining"] = secs
        await message.reply_text(f"✏️ تم تعديل الوقت لكل مداخلة إلى: {fmt_hms(secs)}")
        return

    # ---------------------
    # أوامر أثناء الجلسة (بدون /) — فعّالة إذا كانت المرحلة ready أو running
    # ---------------------
    # بدء العد
    if cmd == "ابدأ الوقت" and data["stage"] == "ready":
        data["stage"] = "running"
        data["paused"] = False
        data["overtime"] = 0
        data["last_update_counter"] = 0
        data["overtime_alert_sent"] = False
        await message.reply_text("⏳ تم بدء المناظرة!")
        # شغّل المهمة الخلفية لعدّ الثواني
        asyncio.create_task(run_timer(chat_id, context.application))
        return

    # عرض الوقت المتبقي
    if cmd == "الوقت المتبقي" and data["stage"] in {"running","ready"}:
        await message.reply_text(build_status_text(data))
        return

    # ايقاف مؤقت
    if cmd == "توقف" and data["stage"] == "running":
        if data["paused"]:
            await message.reply_text("⚠️ المؤقت متوقف بالفعل.")
            return
        data["paused"] = True
        await message.reply_text(f"⏸️ تم إيقاف المؤقت مؤقتًا.\n⏱️ الوقت الحالي: {fmt_hms(data['remaining'])}")
        return

    # استئناف
    if cmd == "استئناف" and data["stage"] == "running":
        if not data["paused"]:
            await message.reply_text("⚠️ المؤقت يعمل بالفعل.")
            return
        data["paused"] = False
        await message.reply_text(f"▶️ تم استئناف المؤقت.\nالمتحدث الآن: {data['current_speaker']}")
        return

    # تنازل => ينهى مداخلة الحالي وينتقل للآخر فورًا
    if cmd == "تنازل" and data["stage"] == "running":
        prev = data["current_speaker"]
        # عدّ المداخلة كتم استخدامها
        data["turns"][prev] = data["turns"].get(prev,0) + 1
        # انتقل
        data["current_speaker"] = data["alt_speaker"]()
        data["remaining"] = data["duration"]
        data["round"] += 1
        data["overtime"] = 0
        data["overtime_alert_sent"] = False
        await message.reply_text(f"🙋‍♂️ {prev} تنازل عن وقته.\n🔁 الدور الآن: {data['current_speaker']}")
        return

    # تبديل يدوي
    if cmd == "تبديل" and data["stage"] == "running":
        prev = data["current_speaker"]
        data["turns"][prev] = data["turns"].get(prev,0) + 1
        data["current_speaker"] = data["alt_speaker"]()
        data["remaining"] = data["duration"]
        data["round"] += 1
        data["overtime"] = 0
        data["overtime_alert_sent"] = False
        await message.reply_text(f"🔁 تم التبديل! المتحدث الآن: {data['current_speaker']}")
        return

    # اعادة وقت المداخلة
    if cmd == "اعادة" and data["stage"] == "running":
        data["remaining"] = data["duration"]
        data["overtime"] = 0
        data["overtime_alert_sent"] = False
        await message.reply_text(f"🔄 تم إعادة وقت المداخلة من البداية.\nالمتحدث الآن: {data['current_speaker']}")
        return

    # اضف / انقص
    m = re.match(r'^(اضف|انقص)\s*([\d٠١٢٣٤٥٦٧٨٩]+)\s*(ث|د)$', to_latin_digits(cmd))
    if m and data["stage"] == "running":
        action = m.group(1)
        num = int(m.group(2))
        unit = m.group(3)
        secs = num if unit == "ث" else num*60
        if action == "اضف":
            data["remaining"] += secs
            await message.reply_text(f"⏱️ تم اضف {fmt_hms(secs)}. الوقت الحالي للمتحدث: {fmt_hms(data['remaining'])}")
        else:
            data["remaining"] -= secs
            if data["remaining"] < 0:
                # يتحول لبداية تجاوز الوقت
                data["overtime"] = abs(data["remaining"])
                data["remaining"] = 0
            await message.reply_text(f"⏱️ تم انقص {fmt_hms(secs)}. الوقت الحالي للمتحدث: {fmt_hms(data['remaining'])}")
        return

    # نهاية المناظرة
    if cmd == "نهاية":
        # حساب النتائج
        s1 = data["speaker1"]
        s2 = data["speaker2"]
        t1_turns = data["turns"].get(s1,0)
        t2_turns = data["turns"].get(s2,0)
        # تقدير الوقت المستخدم: كل مداخلة كاملة = duration، وندمج الوقت الجاري كمستخدم جزئي
        # هذا تقدير تقريبي: الوقت المستخدم = (turns * duration) + (duration - remaining) إذا كان المتحدث الحالي هو نفس الشخص
        def used_time_for(s):
            used = data["turns"].get(s,0) * data["duration"]
            if data["current_speaker"] == s and data["stage"] == "running":
                used += (data["duration"] - max(0,data["remaining"]))
            return used
        u1 = used_time_for(s1)
        u2 = used_time_for(s2)
        total = u1 + u2
        # بناء النص النهائي
        res = f"📊 نتائج المناظرة: {data['title']}\n\n"
        res += f"🟢 {s1}\n🗣️ عدد المداخلات: {t1_turns}\n⏱️ الوقت المستخدم: {fmt_hms(int(u1))}\n\n"
        res += f"🔵 {s2}\n🗣️ عدد المداخلات: {t2_turns}\n⏱️ الوقت المستخدم: {fmt_hms(int(u2))}\n\n"
        res += f"🕒 الوقت الكلي: {fmt_hms(int(total))}\n━━━━━━━━━━━━━━━━━━"
        await message.reply_text(res)
        # اغلاق الجلسة
        debates.pop(chat_id, None)
        return

    # إذا وصلنا هنا ولم يتم التعرف على الأمر
    # لا نرد على رسائل الأعضاء العاديين، ولكن على المشرفين نجاوب برسالة مساعدة
    if await is_admin(chat_id, user.id, context.application):
        await message.reply_text("⚠️ أمر غير معروف. استخدم أحد الأوامر التالية:\n"
                                 "تبديل، توقف، استئناف، تنازل، اضف ٣٠ث، اضف ٢د، انقص ١٥ث، انقص ٢د، اعادة، الوقت المتبقي، نهاية\n"
                                 "أو استخدم صيغ التعديل أثناء التسجيل: تعديل العنوان: ...  تعديل محاور1: ...  تعديل محاور2: ...  تعديل الوقت: 5د")
    return

# ---------------------
# تهيئة التطبيق وتشغيله
# ---------------------
if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    # نضيف معالج الرسائل لجميع النصوص في المجموعة المحددة
    application.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.TEXT & ~filters.COMMAND, handle_text))

    # شغّل Flask في Thread منفصل ليبقي الخدمة حية
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT)).start()

    # شغّل البوت (polling)
    application.run_polling()
