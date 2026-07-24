"""
🤖 Birlashtirilgan Bot — Navbatchi + Ovqat So'rovnoma
=======================================================
Ikki bot bitta faylda ishlaydi:
  1. Navbatchi bot — har kuni soat 12:30 da navbatchilarni e'lon qiladi
  2. Ovqat so'rovnoma — har kuni soat 18:00 da ertangi tushlik so'rovini yuboradi

Buyruqlar:
  /start       — xodim ro'yxatga kiradi (ID saqlanadi)
  /royxat      — barcha xodimlar ro'yxati (admin)
  /boshqaruv   — navbatchi jadvalini tugmali boshqarish (admin):
                 xodim qo'shish/o'chirish, navbatni ko'rish, hafta almashtirish
  /test        — navbatchi xabarini hozir yuborish (test)
  /surov       — ovqat so'rovini hozir yuborish (test, admin)
  /bugun       — bugungi ovqat natijasi (admin)
  /statistika  — haftalik ovqat statistikasi (admin)
  /id          — chat va user ID larini ko'rish
"""

import asyncio
import fcntl
import html
import json
import logging
import os
import random
import re
import sys
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Conflict, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from dotenv import load_dotenv
load_dotenv()  # .env faylidan maxfiy sozlamalarni yuklaydi

# ═══════════════════════════════════════════════════════
#  UMUMIY SOZLAMALAR
# ═══════════════════════════════════════════════════════
BOT_TOKEN         = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("XATO: BOT_TOKEN topilmadi. .env faylini tekshiring.")
CHAT_ID           = -1003232305133      # Guruh ID (navbatchi uchun)
GROUP_ID          = CHAT_ID            # Guruh ID (ovqat uchun — bir xil)
MESSAGE_THREAD_ID = 5702                # Topik ID (navbatchi uchun)
ADMIN_IDS         = [6664377626]
TIMEZONE          = ZoneInfo("Asia/Tashkent")

# ─── Navbatchi vaqti ───
NAVBAT_SOAT  = 12
NAVBAT_MINUT = 30

# ─── Ovqat vaqti ───
OPEN_HOUR  = 18   # So'rov 18:00 da keladi
CLOSE_HOUR = 6   # Ertalab 6:00 da yopiladi

# Admin avtomatik "ha" bosganda ismi
ADMIN_NAMES = {
    6664377626: "Jamshid",
    1164609696: "Numonjon",
    6215451224: "Ozodbek",
    7656548055: "Ismoil",
}

XODIMLAR_FILE = "xodimlar.json"
VAQT_ADMIN_FILE = "vaqtinchalik_adminlar.json"   # Vaqtinchalik adminlar ro'yxati
DATA_FILE     = "ovqat_data.json"
JADVAL_FILE   = "jadval.json"          # Navbatchi jadvali (2 guruh + rotatsiya)
MENU_FILE     = "menu.json"            # Haftalik taomlar ro'yxati (admin tahrirlashi mumkin)
LOCK_FILE     = "navbatchi_bot.lock"   # Yagona-nusxa qulfi

# Hafta rotatsiyasi uchun bazaviy dushanba (continuous hafta hisoblash uchun)
EPOCH_MONDAY = date(2024, 1, 1)        # Dushanba
# Navbatchi kunlari (Yakshanba — dam olish, jadvalga kirmaydi)
KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]

HAFTA_KUNLARI = {
    0: "Dushanba", 1: "Seshanba", 2: "Chorshanba",
    3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba",
}
WEEKDAY_UZ = ["Dushanba","Seshanba","Chorshanba","Payshanba","Juma","Shanba","Yakshanba"]

# ═══════════════════════════════════════════════════════
#  NAVBATCHI JADVALI
# ═══════════════════════════════════════════════════════
HAFTALIK_JADVAL = {
    "Dushanba": [
        ("Farangiz Murtazaqulov",  6605911243),
        ("Jasmina Elmuratova",     7603976019),
        ("Firdavs Hamidov",        7109729589),
        ("Shaxnoza Arslonova",     7281226843),
        ("O'ktam Sayfullayev",     483923764),
    ],
    "Seshanba": [
        ("Gulzoda Rahmonova",      6332222917),
        ("Ruxshona Beshimova",     8002918423),
        ("Bobur Anvarov",          920076870),
        ("Mubina Isahójava",       None),
        ("Sanjar Jumaboyev",       5369355635),
    ],
    "Chorshanba": [
        ("Azizaxon Xayitova",      8302294629),
        ("Zuxra Muhiddinova",      None),
        ("Muazzam Murtazayeva",    7482810648),
        ("Temur Gafforov",         None),
        ("Usmon Salimov",          None),
    ],
    "Payshanba": [
        ("Dinora Ahmedov",         7211771006),
        ("Ziyoda Shamsiyeva",      7145159625),
        ("Ziyoda Saidova",          7039811540),
        ("Komola Eshmamatova",     6077939024),
        ("Boburmirzo Nasriddinov", None),
    ],
    "Juma": [
        ("Aziza Muhammadlatipova", 8228579796),
        ("Rano Muhammadjonova",    None),
        ("Risolat Xasanova",       None),
        ("Dilbar Qodirova",        None),
        ("Ramziddin Allayorov",  5358452332),
    ],
    "Shanba": [
        ("Fotima Isakova",         8302746200),
        ("Durdona Samiljonova",    6824049901),
        ("Akmalova Jasmina",       8117042356),
        ("Xojimurod Tokliyev",     1305445150),
        ("Choriyev Diyor",         8138849461),
    ],
}

# ═══════════════════════════════════════════════════════
#  OVQAT MENYUSI
# ═══════════════════════════════════════════════════════
DEFAULT_MENU = {
    0: {"name": "Golubsi yoki Pelmeni", "photo": "photos/dushanba.jpg"},
    1: {"name": "Tovuq jarkop",         "photo": "photos/seshanba.jpg"},
    2: {"name": "Lag'mon",              "photo": "photos/chorshanba.jpg"},
    3: {"name": "Osh (Plov)",           "photo": "photos/payshanba.jpg"},
    4: {"name": "Mastava",              "photo": "photos/juma.jpg"},
    5: {"name": "Mosh kichiri",         "photo": "photos/shanba.jpg"},
}

# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#  YAGONA-NUSXA QULFI
# ──────────────────────────────────────────────────────
# Faylga eksklyuziv flock qo'yamiz. Ikkinchi nusxa ishga tushsa,
# flock olib bo'lmaydi va jarayon darhol to'xtaydi. Bu Telegram'dagi
# "409 Conflict: terminated by other getUpdates request" sababini
# (bir vaqtda ikkita bot) butunlay yo'q qiladi.
_lock_handle = None  # GC fayl deskriptorini yopib qulfni bo'shatmasligi uchun saqlaymiz

def acquire_single_instance_lock():
    global _lock_handle
    _lock_handle = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error(
            "⛔ Bot allaqachon ishlamoqda (%s qulflangan). "
            "Ikkinchi nusxa ishga tushmaydi.", LOCK_FILE
        )
        sys.exit(1)
    _lock_handle.write(str(os.getpid()))
    _lock_handle.flush()
    logger.info("🔒 Yagona-nusxa qulfi olindi (PID %s)", os.getpid())


# ──────────────────────────────────────────────────────
#  XATOLARNI USHLOVCHI (error handler)
# ──────────────────────────────────────────────────────
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    err = ctx.error
    # Conflict — bir vaqtda ikkinchi nusxa polling qilyapti.
    # Qulf buni oldini oladi, lekin baribir log'ni bosib ketmasligi uchun
    # ushlab, qisqa ogohlantirish beramiz.
    if isinstance(err, Conflict):
        logger.error(
            "⚠️ Conflict: boshqa bot nusxasi getUpdates qilyapti. "
            "Faqat bitta nusxa ishlayotganiga ishonch hosil qiling."
        )
        return
    if isinstance(err, NetworkError):
        logger.warning("🌐 Tarmoq xatosi (vaqtincha): %s", err)
        return
    logger.error("❌ Ushlangan xato: %s", err, exc_info=err)


# ──────────────────────────────────────────────────────
#  YORDAMCHI FUNKSIYALAR
# ──────────────────────────────────────────────────────
def load_vaqt_adminlar() -> dict:
    if os.path.exists(VAQT_ADMIN_FILE):
        try:
            with open(VAQT_ADMIN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_vaqt_adminlar(data: dict):
    with open(VAQT_ADMIN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_super_admin(user_id: int) -> bool:
    """Doimiy (bosh) admin — faqat shular vaqtinchalik admin qo'sha/o'chira oladi."""
    return user_id in ADMIN_IDS

def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return str(user_id) in load_vaqt_adminlar()

def tomorrow_str() -> str:
    tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
    return tomorrow.strftime("%Y-%m-%d")

def today_str() -> str:
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

def yesterday_str() -> str:
    kecha = datetime.now(TIMEZONE).date() - timedelta(days=1)
    return kecha.strftime("%Y-%m-%d")

def is_open() -> bool:
    now_hour = datetime.now(TIMEZONE).hour
    if OPEN_HOUR < CLOSE_HOUR:
        # Oddiy holat (bir kun ichida)
        return OPEN_HOUR <= now_hour < CLOSE_HOUR
    # Oraliq yarim tunni kesib o'tadi: 18:00 dan ertasi 06:00 gacha
    return now_hour >= OPEN_HOUR or now_hour < CLOSE_HOUR

def load_menu() -> dict:
    """Haftalik taomlar ro'yxati. menu.json bo'lmasa yoki kun yo'q bo'lsa,
    standart (DEFAULT_MENU) taom qo'llaniladi."""
    menu = {wd: dict(info) for wd, info in DEFAULT_MENU.items()}
    if os.path.exists(MENU_FILE):
        try:
            with open(MENU_FILE, "r", encoding="utf-8") as f:
                saqlangan = json.load(f)
            for k, v in saqlangan.items():
                menu[int(k)] = v
        except Exception:
            pass
    return menu

def save_menu(menu: dict):
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in menu.items()}, f, ensure_ascii=False, indent=2)

def get_next_menu():
    menu = load_menu()
    weekday = datetime.now(TIMEZONE).weekday()
    if weekday == 6:
        return menu.get(0), WEEKDAY_UZ[0]
    if weekday == 5:
        return None, None
    next_weekday = (weekday + 1) % 7
    return menu.get(next_weekday), WEEKDAY_UZ[next_weekday]


# ──────────────────────────────────────────────────────
#  XODIMLAR (navbatchi) — JSON
# ──────────────────────────────────────────────────────
def load_xodimlar() -> dict:
    if os.path.exists(XODIMLAR_FILE):
        try:
            with open(XODIMLAR_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_xodimlar(data: dict):
    with open(XODIMLAR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def remember_user(user) -> None:
    """Foydalanuvchini xodimlar ro'yxatiga eslab qoladi (ID + ism).
    /start dan tashqari tugma bosilganda ham chaqiriladi — shunda
    keyinchalik navbatga qo'shish uchun ID tayyor turadi."""
    if not user:
        return
    uid = str(user.id)
    xodimlar = load_xodimlar()
    yangi = {
        "name":     user.full_name,
        "username": f"@{user.username}" if user.username else "",
    }
    if xodimlar.get(uid) != yangi:
        xodimlar[uid] = yangi
        save_xodimlar(xodimlar)


# ──────────────────────────────────────────────────────
#  NAVBATCHI JADVALI — JSON (2 guruh + hafta rotatsiyasi)
# ──────────────────────────────────────────────────────
def _init_jadval() -> dict:
    """Birinchi marta: ikkala hafta ham bo'sh yaratiladi.
    Admin bot orqali matnli ro'yxat yuklaydi, xodimlar o'z ismini tanlaydi."""
    return {
        "offset": 0,   # "🔄 Hafta almashtirish" shu sonni o'zgartiradi
        "guruhlar": [
            {"nom": "1-hafta", "kunlar": {kun: [] for kun in KUNLAR}},
            {"nom": "2-hafta", "kunlar": {kun: [] for kun in KUNLAR}},
        ],
    }

# Har kunga nechta navbatchi joylashtiriladi (matnli ro'yxat yuklashda)
PER_DAY = 5

def royxatni_joylashtir(j: dict, gi: int, ismlar: list) -> tuple:
    """Berilgan ismlarni guruhning kunlariga ketma-ket PER_DAY tadan joylaydi.
    Avval band qilingan ID'lar (xuddi shu ism uchun) saqlanib qoladi."""
    eski_id = {}
    for lst in j["guruhlar"][gi]["kunlar"].values():
        for x in lst:
            if x.get("id"):
                eski_id[x["ism"]] = x["id"]
    kunlar = {kun: [] for kun in KUNLAR}
    idx = 0
    for kun in KUNLAR:
        for _ in range(PER_DAY):
            if idx < len(ismlar):
                nm = ismlar[idx]
                kunlar[kun].append({"ism": nm, "id": eski_id.get(nm)})
                idx += 1
    j["guruhlar"][gi]["kunlar"] = kunlar
    return idx, len(ismlar)   # (joylashtirilgan, jami)

def load_jadval() -> dict:
    if os.path.exists(JADVAL_FILE):
        try:
            with open(JADVAL_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception:
            pass
    j = _init_jadval()
    save_jadval(j)
    return j

def save_jadval(data: dict):
    with open(JADVAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hafta_raqami() -> int:
    """Bazaviy dushanbadan beri o'tgan haftalar soni (continuous)."""
    bugun = datetime.now(TIMEZONE).date()
    return (bugun - EPOCH_MONDAY).days // 7

def aktiv_guruh_index(j: dict | None = None) -> int:
    """Shu hafta navbatchi bo'lgan guruh indeksi."""
    if j is None:
        j = load_jadval()
    n = len(j["guruhlar"]) or 1
    return (hafta_raqami() + j.get("offset", 0)) % n


# ──────────────────────────────────────────────────────
#  OVQAT DATA — JSON
# ──────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception:
            return {}
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────
#  OVQAT — Klaviaturalar
# ──────────────────────────────────────────────────────
def get_survey_keyboard(bugun: str):
    data      = load_data()
    kun_data  = data.get(bugun, {})
    ha_count  = sum(1 for v in kun_data.values() if v["answer"] == "ha")
    yoq_count = sum(1 for v in kun_data.values() if v["answer"] == "yoq")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ HA ({ha_count})",    callback_data=f"ha_{bugun}"),
        InlineKeyboardButton(f"❌ Yo'q ({yoq_count})", callback_data=f"yoq_{bugun}"),
    ]])

def get_list_keyboard(bugun: str):
    data      = load_data()
    kun_data  = data.get(bugun, {})
    ha_count  = sum(1 for v in kun_data.values() if v["answer"] == "ha")
    yoq_count = sum(1 for v in kun_data.values() if v["answer"] == "yoq")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ HA: {ha_count} kishi",    callback_data=f"list_ha_{bugun}"),
        InlineKeyboardButton(f"❌ Yo'q: {yoq_count} kishi", callback_data=f"list_yoq_{bugun}"),
    ]])


# ══════════════════════════════════════════════════════
#  NAVBATCHI — BUYRUQLAR
# ══════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    remember_user(user)

    j     = load_jadval()
    slots = unclaimed_slots(j)
    if not slots:
        await update.message.reply_text(
            "📭 Hozircha ro'yxat bo'sh. Keyinroq /start bosing."
        )
        logger.info("/start: %s (%s) — ro'yxat bo'sh", user.full_name, user.id)
        return

    await update.message.reply_text(
        f"📝 Ro'yxatdan o'z ismingizni tanlang ({len(slots)} ta bo'sh):",
        reply_markup=claim_picker_kb(slots, 0),
    )
    logger.info("/start: %s (%s) — ro'yxat ko'rsatildi", user.full_name, user.id)


async def royxat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    xodimlar = load_xodimlar()
    if not xodimlar:
        await update.message.reply_text("📭 Hali hech kim /start bosmagan.")
        return

    text = "📋 <b>Ro'yxatga kirganlar:</b>\n\n"
    for uid, info in xodimlar.items():
        text += f"• {html.escape(info['name'])} — ID: <code>{uid}</code>\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def navbat_xabar_yuborish(app: Application):
    hozir    = datetime.now(TIMEZONE)
    kun_nomi = HAFTA_KUNLARI[hozir.weekday()]

    if hozir.weekday() == 6:
        matn = (
            f"🌟 <b>Yakshanba — Dam olish kuni!</b>\n\n"
            f"📅 {hozir.strftime('%d.%m.%Y')}\n\n"
            f"😊 Barcha xodimlarga yaxshi dam olish tilaymiz!\n"
            f"Ertaga yangi hafta yangi kuch bilan boshlanadi 💪\n\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            await app.bot.send_message(
                chat_id=CHAT_ID,
                message_thread_id=MESSAGE_THREAD_ID,
                text=matn,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Yakshanba xabarida xato: %s", e)
        return

    j            = load_jadval()
    gi           = aktiv_guruh_index(j)
    guruh        = j["guruhlar"][gi]
    navbatchilar = guruh["kunlar"].get(kun_nomi, [])

    matn = (
        f"🔔 <b>Bugungi navbatchilar!</b>\n\n"
        f"📅 {html.escape(kun_nomi)}, {hozir.strftime('%d.%m.%Y')}\n"
        f"👥 Navbatchi guruh: <b>{html.escape(guruh['nom'])}</b>\n\n"
        f"⏰ Ish boshlanishi: {NAVBAT_SOAT:02d}:{NAVBAT_MINUT:02d}\n\n"
    )

    if not navbatchilar:
        matn += "<i>(Bu kunga navbatchi belgilanmagan)</i>\n"
    for i, x in enumerate(navbatchilar, start=1):
        ism = x.get("ism", "")
        uid = x.get("id")
        if uid:
            matn += f'👤 {i}. <a href="tg://user?id={uid}">{html.escape(ism)}</a>\n'
        else:
            matn += f"👤 {i}. {html.escape(ism)}\n"

    matn += (
        f"\n✅ O'z vazifangizni o'z vaqtida bajaring!\n"
        f"Mas'uliyat birinchi o'rinda! 💼\n\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            message_thread_id=MESSAGE_THREAD_ID,
            text=matn,
            parse_mode="HTML",
        )
        logger.info("Navbatchi xabari yuborildi: %s", kun_nomi)
    except Exception as e:
        logger.error("Xabar yuborishda xato: %s", e)


async def test(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await navbat_xabar_yuborish(ctx.application)
    await update.message.reply_text("📨 Test xabari yuborildi.")


# ══════════════════════════════════════════════════════
#  OVQAT — FUNKSIYALAR
# ══════════════════════════════════════════════════════

async def auto_vote_admin(app: Application, bugun: str):
    wait_seconds = random.randint(60, 10800)
    logger.info("Admin avtomatik ovoz %d sekunddan keyin beriladi", wait_seconds)
    await asyncio.sleep(wait_seconds)

    data = load_data()
    if bugun not in data:
        data[bugun] = {}

    for admin_id in ADMIN_IDS:
        uid = str(admin_id)
        if uid not in data[bugun]:
            ism = ADMIN_NAMES.get(admin_id, "Admin")
            data[bugun][uid] = {
                "name":   ism,
                "answer": "ha",
                "time":   datetime.now(TIMEZONE).strftime("%H:%M"),
            }
            logger.info("Admin %s (%s) avtomatik 'ha' deb belgilandi", ism, admin_id)

    save_data(data)


async def send_daily_survey(app: Application):
    menu, kun = get_next_menu()
    if not menu or not kun:
        logger.info("Bugun so'rov kelmaydi (Shanba).")
        return

    bugun = tomorrow_str()
    text  = (
        f"🍽 <b>Ertaga {html.escape(kun)} tushlik — 🍜{html.escape(menu['name'])}</b>\n\n"
        f"Tanovvul qilaszmi?\n"
        f"⏰ Soat {CLOSE_HOUR:02d}:00 gacha javob bering!"
    )
    try:
        photo_path = menu["photo"]
        keyboard   = get_survey_keyboard(bugun)
        if os.path.exists(photo_path):
            with open(photo_path, "rb") as photo:
                await app.bot.send_photo(
                    chat_id=GROUP_ID, photo=photo,message_thread_id=MESSAGE_THREAD_ID,
                    caption=text, parse_mode="HTML",
                    reply_markup=keyboard,
                )
        else:
            await app.bot.send_message(
                chat_id=GROUP_ID,message_thread_id=MESSAGE_THREAD_ID,
                text=text + "\n\n<i>(⚠️ Rasm yuklanmagan)</i>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        logger.info("So'rov yuborildi: ertaga %s", kun)
        asyncio.create_task(auto_vote_admin(app, bugun))
    except Exception as e:
        logger.error("So'rov yuborishda xato: %s", e)
        return

    xodimlar    = load_xodimlar()
    xodim_ids   = {int(uid) for uid in xodimlar.keys()}
    recipients  = xodim_ids | set(ADMIN_IDS)

    for user_id in recipients:
        try:
            personal_keyboard = get_survey_keyboard(bugun)
            if os.path.exists(photo_path):
                with open(photo_path, "rb") as photo:
                    await app.bot.send_photo(
                        chat_id=user_id, photo=photo,
                        caption=text, parse_mode="HTML",
                        reply_markup=personal_keyboard,
                    )
            else:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=text + "\n\n<i>(⚠️ Rasm yuklanmagan)</i>",
                    parse_mode="HTML",
                    reply_markup=personal_keyboard,
                )
        except Exception as e:
            logger.error("So'rovni xodimga (%s) yuborishda xato: %s", user_id, e)


async def send_voting_results(app: Application):
    """Ovoz berish vaqti tugagach (CLOSE_HOUR) yeydigan/yemaydiganlar
    ro'yxatini guruhga yuboradi. Ovozlar bugungi sana kaliti ostida saqlanadi."""
    bugun    = today_str()
    data     = load_data()
    kun_data = data.get(bugun, {})

    if not kun_data:
        logger.info("Yopilish natijasi: %s uchun ovoz yo'q, yuborilmadi.", bugun)
        return

    weekday = datetime.now(TIMEZONE).weekday()
    menu    = load_menu().get(weekday)
    ovqat   = menu["name"] if menu else "—"
    kun     = WEEKDAY_UZ[weekday]

    ha_list  = [v["name"] for v in kun_data.values() if v["answer"] == "ha"]
    yoq_list = [v["name"] for v in kun_data.values() if v["answer"] == "yoq"]

    text  = (
        f"📊 <b>Ovoz berish yakunlandi!</b>\n"
        f"📅 {html.escape(kun)} — 🍽 {html.escape(ovqat)}\n\n"
        f"✅ <b>Yeydiganlar ({len(ha_list)} kishi):</b>\n"
    )
    text += "\n".join(f"{i+1}. {html.escape(ism)}" for i, ism in enumerate(ha_list)) or "— hech kim —"
    text += f"\n\n❌ <b>Yemaydiganlar ({len(yoq_list)} kishi):</b>\n"
    text += "\n".join(f"{i+1}. {html.escape(ism)}" for i, ism in enumerate(yoq_list)) or "— hech kim —"
    text += f"\n\n━━━━━━━━━━━━━━━━━━━━\n📝 Jami: {len(kun_data)} ta javob"

    try:
        await app.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=MESSAGE_THREAD_ID,
            text=text,
            parse_mode="HTML",
        )
        logger.info("Yopilish natijasi yuborildi: %s (✅ %d / ❌ %d)",
                    bugun, len(ha_list), len(yoq_list))
    except Exception as e:
        logger.error("Yopilish natijasini yuborishda xato: %s", e)


async def send_weekly_food_report(app: Application):
    """Haftalik 6 kunlik (Dushanba–Shanba) ovqat hisobotini guruhga yuboradi.
    Faqat raqamlar: har kun nechta yedi/yemadi va hafta jami."""
    data   = load_data()
    today  = datetime.now(TIMEZONE).date()
    monday = today - timedelta(days=today.weekday())
    kunlar = [monday + timedelta(days=i) for i in range(6)]  # Dush–Shanba

    hafta_boshi = monday.strftime("%d.%m")
    hafta_oxiri = (monday + timedelta(days=5)).strftime("%d.%m.%Y")

    text = (
        f"📊 <b>Haftalik ovqat hisoboti</b>\n"
        f"📅 {hafta_boshi} – {hafta_oxiri}\n\n"
    )

    jami_yedi = jami_yemadi = 0
    for i, kun in enumerate(kunlar):
        kun_str   = kun.strftime("%Y-%m-%d")
        kun_data  = data.get(kun_str, {})
        ha_count  = sum(1 for v in kun_data.values() if v["answer"] == "ha")
        yoq_count = sum(1 for v in kun_data.values() if v["answer"] == "yoq")
        text += f"<b>{WEEKDAY_UZ[i]}:</b> ✅ {ha_count}  |  ❌ {yoq_count}\n"
        jami_yedi   += ha_count
        jami_yemadi += yoq_count

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🍽 <b>Hafta jami:</b> ✅ {jami_yedi} ta yedi  |  ❌ {jami_yemadi} ta yemadi"
    )

    try:
        await app.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=MESSAGE_THREAD_ID,
            text=text,
            parse_mode="HTML",
        )
        logger.info("Haftalik hisobot yuborildi: %s – %s (✅ %d / ❌ %d)",
                    hafta_boshi, hafta_oxiri, jami_yedi, jami_yemadi)
    except Exception as e:
        logger.error("Haftalik hisobotni yuborishda xato: %s", e)


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user     = query.from_user
    data_str = query.data

    remember_user(user)

    if data_str.startswith("list_"):
        parts    = data_str.split("_", 2)
        javob    = parts[1]
        bugun    = parts[2]
        data     = load_data()
        kun_data = data.get(bugun, {})
        ismlar   = [v["name"] for v in kun_data.values() if v["answer"] == javob]

        if javob == "ha":
            text = f"✅ <b>Yeyman deganlar ({len(ismlar)} kishi):</b>\n\n"
        else:
            text = f"❌ <b>Yemayman deganlar ({len(ismlar)} kishi):</b>\n\n"
        text += "\n".join(f"{i+1}. {html.escape(ism)}" for i, ism in enumerate(ismlar)) or "— hech kim —"

        await query.answer()
        await query.message.reply_text(text, parse_mode="HTML")
        return

    parts = data_str.split("_", 1)
    javob = parts[0]
    bugun = parts[1] if len(parts) > 1 else today_str()

    if not is_open():
        await query.answer(
            f"⏰ Vaqt tugadi! {CLOSE_HOUR:02d}:00 dan keyin qabul qilinmaydi.",
            show_alert=True,
        )
        return

    data = load_data()
    uid  = str(user.id)

    if bugun not in data:
        data[bugun] = {}

    # Oldingi javobni eslab qolamiz — adashib bosgan bo'lsa almashtira oladi
    oldingi = data[bugun].get(uid, {}).get("answer")

    data[bugun][uid] = {
        "name":   user.full_name,
        "answer": javob,
        "time":   datetime.now(TIMEZONE).strftime("%H:%M"),
    }
    save_data(data)

    try:
        await query.edit_message_reply_markup(
            reply_markup=get_survey_keyboard(bugun)
        )
    except Exception:
        pass

    if oldingi is None:
        # Birinchi marta ovoz berdi
        msg = "✅ Ro'yxatga kiritildingiz!" if javob == "ha" else "❌ Yozib qo'yildi."
    elif oldingi == javob:
        # Xuddi shu javobni qayta bosdi — o'zgarish yo'q
        msg = ("✅ Siz allaqachon «Yeyman» deb belgilangansiz."
               if javob == "ha" else
               "❌ Siz allaqachon «Yemayman» deb belgilangansiz.")
    else:
        # Javobini almashtirdi (adashib bosgan bo'lsa to'g'irladi)
        msg = ("🔄 Javobingiz o'zgartirildi: ✅ Yeyman"
               if javob == "ha" else
               "🔄 Javobingiz o'zgartirildi: ❌ Yemayman")
    await query.answer(msg, show_alert=True)
    logger.info("%s (%s) → %s (oldingi: %s)", user.full_name, user.id, javob, oldingi)


async def statistika(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Faqat adminlar uchun.")
        return

    data   = load_data()
    today  = datetime.now(TIMEZONE).date()
    monday = today - timedelta(days=today.weekday())
    kunlar = [monday + timedelta(days=i) for i in range(6)]

    hafta_boshi = monday.strftime("%d.%m")
    hafta_oxiri = (monday + timedelta(days=5)).strftime("%d.%m.%Y")
    text = f"📊 <b>Haftalik statistika</b>\n<i>{hafta_boshi} – {hafta_oxiri}</i>\n\n"

    jami_yedi = jami_yemadi = 0
    for i, kun in enumerate(kunlar):
        kun_str   = kun.strftime("%Y-%m-%d")
        kun_data  = data.get(kun_str, {})
        ha_count  = sum(1 for v in kun_data.values() if v["answer"] == "ha")
        yoq_count = sum(1 for v in kun_data.values() if v["answer"] == "yoq")
        text += f"<b>{WEEKDAY_UZ[i]}:</b> ✅ {ha_count} ha  |  ❌ {yoq_count} yuq\n"
        jami_yedi   += ha_count
        jami_yemadi += yoq_count

    text += f"\n🍽 Hafta jami: <b>{jami_yedi} ta</b> Tanavvul qildi  |  <b>{jami_yemadi} ta</b> Tanavvul qilmadi"
    await update.message.reply_text(text, parse_mode="HTML")


async def bugun_natija(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Faqat adminlar uchun.")
        return

    data     = load_data()
    bugun    = today_str()
    kun_data = data.get(bugun, {})
    weekday  = datetime.now(TIMEZONE).weekday()
    menu     = load_menu().get(weekday)
    ovqat    = menu["name"] if menu else "—"
    kun      = WEEKDAY_UZ[weekday]

    ha_count  = sum(1 for v in kun_data.values() if v["answer"] == "ha")
    yoq_count = sum(1 for v in kun_data.values() if v["answer"] == "yoq")

    text = (
        f"📋 <b>Bugun: {html.escape(kun)} — {html.escape(ovqat)}</b>\n\n"
        f"✅ Yeyman: <b>{ha_count} kishi</b>\n"
        f"❌ Yemayman: <b>{yoq_count} kishi</b>\n"
        f"📝 Jami: {len(kun_data)} ta javob"
    )
    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=get_list_keyboard(bugun),
    )


def build_results_text(kun_key: str) -> str:
    """Berilgan sana (YYYY-MM-DD) uchun kim yeydi / kim yemaydi — to'liq
    ism ro'yxatini HTML matn ko'rinishida tuzadi."""
    data     = load_data()
    kun_data = data.get(kun_key, {})
    d        = datetime.strptime(kun_key, "%Y-%m-%d").date()
    weekday  = d.weekday()
    menu     = load_menu().get(weekday)
    ovqat    = menu["name"] if menu else "—"
    kun      = WEEKDAY_UZ[weekday]
    sana     = d.strftime("%d.%m.%Y")

    if not kun_data:
        return (f"📅 <b>{html.escape(kun)}, {sana}</b> — 🍽 {html.escape(ovqat)}\n\n"
                f"— Bu kunga hech kim ovoz bermagan —")

    ha_list  = [v["name"] for v in kun_data.values() if v["answer"] == "ha"]
    yoq_list = [v["name"] for v in kun_data.values() if v["answer"] == "yoq"]

    text  = (
        f"📊 <b>{html.escape(kun)}, {sana}</b> — 🍽 {html.escape(ovqat)}\n\n"
        f"✅ <b>Yeydiganlar ({len(ha_list)} kishi):</b>\n"
    )
    text += "\n".join(f"{i+1}. {html.escape(ism)}" for i, ism in enumerate(ha_list)) or "— hech kim —"
    text += f"\n\n❌ <b>Yemaydiganlar ({len(yoq_list)} kishi):</b>\n"
    text += "\n".join(f"{i+1}. {html.escape(ism)}" for i, ism in enumerate(yoq_list)) or "— hech kim —"
    text += f"\n\n━━━━━━━━━━━━━━━━━━━━\n📝 Jami: {len(kun_data)} ta javob"
    return text


async def kecha_natija(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/kecha — bugungi kundan bir kun oldingi (kechagi) ovqatga kim bosgan/
    bosmaganini ism bilan ko'rsatadi."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Faqat adminlar uchun.")
        return
    kun_key = yesterday_str()
    try:
        await update.message.reply_text(
            build_results_text(kun_key),
            parse_mode="HTML",
        )
        logger.info("/kecha yuborildi: %s", kun_key)
    except Exception as e:
        logger.error("/kecha (%s) yuborishda xato: %s", kun_key, e)
        await update.message.reply_text(
            f"⚠️ Kechagi natijani ko'rsatishda xatolik: {e}"
        )


async def surov(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Faqat adminlar uchun.")
        return
    await send_daily_survey(ctx.application)
    await update.message.reply_text("📨 So'rov yuborildi.")


async def natija(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Faqat adminlar uchun.")
        return
    await send_voting_results(ctx.application)
    await update.message.reply_text("📨 Natija ro'yxati yuborildi.")


async def get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    await update.message.reply_text(
        f"Chat ID: <code>{chat.id}</code> ({chat.type})\nSizning ID: <code>{user.id}</code>",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════
#  NAVBATCHI BOSHQARUVI — TUGMALI MENYU (admin)
# ══════════════════════════════════════════════════════

def menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 1-hafta ro'yxat yuklash", callback_data="up:0")],
        [InlineKeyboardButton("📥 2-hafta ro'yxat yuklash", callback_data="up:1")],
        [InlineKeyboardButton("✏️ Ism almashtirish / qo'shish", callback_data="repl")],
        [InlineKeyboardButton("🔀 Kun almashtirish", callback_data="da:g:src")],
        [InlineKeyboardButton("👥 Navbatni ko'rish", callback_data="mng:view")],
        [InlineKeyboardButton("🔄 Haftani almashtirish", callback_data="mng:swap")],
        [InlineKeyboardButton("🍽 Ovqatni o'zgartirish", callback_data="mnu:menu")],
        [InlineKeyboardButton("👤 Adminlar", callback_data="adm:menu")],
    ])

def back_home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="mng:home")]
    ])

def menu_kunlar_kb():
    menu = load_menu()
    rows = [
        [InlineKeyboardButton(f"{kun} — {menu.get(wd, {}).get('name', '—')}",
                               callback_data=f"mnu:day:{wd}")]
        for wd, kun in enumerate(KUNLAR)
    ]
    rows.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="mng:home")])
    return InlineKeyboardMarkup(rows)

# ── Adminlar (vaqtinchalik) ──
ADM_PAGE = 8

def adm_menu_kb():
    vaqt = load_vaqt_adminlar()
    rows = [
        [InlineKeyboardButton(f"❌ {info.get('name', uid)}", callback_data=f"adm:del:{uid}")]
        for uid, info in vaqt.items()
    ]
    rows.append([InlineKeyboardButton("➕ Admin qo'shish", callback_data="adm:addpage:0")])
    rows.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="mng:home")])
    return InlineKeyboardMarkup(rows)

def adm_add_kb(page: int):
    vaqt     = load_vaqt_adminlar()
    xodimlar = load_xodimlar()
    nomzodlar = [
        (uid, info.get("name", uid)) for uid, info in xodimlar.items()
        if uid not in vaqt and int(uid) not in ADMIN_IDS
    ]
    boshi = page * ADM_PAGE
    chunk = nomzodlar[boshi:boshi + ADM_PAGE]
    rows = [
        [InlineKeyboardButton(nom[:60], callback_data=f"adm:addpick:{uid}")]
        for uid, nom in chunk
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"adm:addpage:{page-1}"))
    if boshi + ADM_PAGE < len(nomzodlar):
        nav.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"adm:addpage:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:menu")])
    return InlineKeyboardMarkup(rows)

def repl_guruh_kb():
    j = load_jadval()
    rows = [
        [InlineKeyboardButton(g["nom"], callback_data=f"rgg:{gi}")]
        for gi, g in enumerate(j["guruhlar"])
    ]
    rows.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="mng:home")])
    return InlineKeyboardMarkup(rows)

def repl_kun_kb(gi: int):
    rows = [
        [InlineKeyboardButton(kun, callback_data=f"rgd:{gi}:{di}")]
        for di, kun in enumerate(KUNLAR)
    ]
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="repl")])
    return InlineKeyboardMarkup(rows)

def repl_slot_kb(gi: int, di: int):
    j   = load_jadval()
    lst = j["guruhlar"][gi]["kunlar"].get(KUNLAR[di], [])
    rows = []
    for idx, x in enumerate(lst):
        belgi = "" if x.get("id") else " ⏳"
        rows.append([InlineKeyboardButton(
            f"{x.get('ism','—')}{belgi}", callback_data=f"rgp:{gi}:{di}:{idx}")])
    rows.append([InlineKeyboardButton("➕ Yangi ism qo'shish", callback_data=f"rgp:{gi}:{di}:-1")])
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"rgg:{gi}")])
    return InlineKeyboardMarkup(rows)

def da_guruh_kb(mode: str):
    """Kun almashtirish — hafta guruhini tanlash (mode: src/dst)."""
    j = load_jadval()
    rows = [
        [InlineKeyboardButton(g["nom"], callback_data=f"da:d:{mode}:{gi}")]
        for gi, g in enumerate(j["guruhlar"])
    ]
    rows.append([InlineKeyboardButton("⬅️ Bekor qilish", callback_data="mng:home")])
    return InlineKeyboardMarkup(rows)

def da_kun_kb(mode: str, gi: int):
    rows = [
        [InlineKeyboardButton(kun, callback_data=f"da:s:{mode}:{gi}:{di}")]
        for di, kun in enumerate(KUNLAR)
    ]
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"da:g:{mode}")])
    return InlineKeyboardMarkup(rows)

def da_slot_kb(mode: str, gi: int, di: int):
    j   = load_jadval()
    lst = j["guruhlar"][gi]["kunlar"].get(KUNLAR[di], [])
    rows = []
    for idx, x in enumerate(lst):
        belgi = "" if x.get("id") else " ⏳"
        rows.append([InlineKeyboardButton(
            f"{x.get('ism','—')}{belgi}", callback_data=f"da:pick:{mode}:{gi}:{di}:{idx}")])
    if mode == "dst":
        rows.append([InlineKeyboardButton(
            "➕ Bo'sh joy (oxiriga qo'shish)", callback_data=f"da:pick:{mode}:{gi}:{di}:-1")])
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"da:d:{mode}:{gi}")])
    return InlineKeyboardMarkup(rows)


def navbat_korinish_matni() -> str:
    """Ikkala haftaning jadvalini va shu hafta kim navbatchi ekanini ko'rsatadi.
    ⏳ = xodim hali o'z ismini tanlamagan (ID bog'lanmagan)."""
    j     = load_jadval()
    aktiv = aktiv_guruh_index(j)
    qatorlar = [
        f"📋 Navbat jadvali  (hafta №{hafta_raqami()})",
        "⏳ = xodim hali /start bosib ismini tanlamagan",
    ]
    for gi, g in enumerate(j["guruhlar"]):
        belgi = "  ✅ SHU HAFTA NAVBATCHI" if gi == aktiv else ""
        qatorlar.append(f"\n👥 {g['nom']}{belgi}")
        for kun in KUNLAR:
            lst = g["kunlar"].get(kun, [])
            if lst:
                ismlar = ", ".join(
                    x.get("ism", "—") + ("" if x.get("id") else " ⏳") for x in lst)
            else:
                ismlar = "—"
            qatorlar.append(f"  • {kun}: {ismlar}")
    return "\n".join(qatorlar)


# ── Xodim o'z ismini tanlash (self-claim) ──
CLAIM_PAGE = 8

def _clean_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^\s*\d+\s*[\.\)\-]\s*", "", s)   # "1. ", "2) ", "3- " kabi raqamlash
    return s.strip(" -•·\t").strip()

def unclaimed_slots(j: dict) -> list:
    """ID bog'lanmagan barcha o'rinlar: (gi, di, idx, ism)."""
    res = []
    for gi, g in enumerate(j["guruhlar"]):
        for di, kun in enumerate(KUNLAR):
            for idx, x in enumerate(g["kunlar"].get(kun, [])):
                if not x.get("id"):
                    res.append((gi, di, idx, x.get("ism", "—")))
    return res

def claim_picker_kb(slots: list, page: int):
    boshi = page * CLAIM_PAGE
    chunk = slots[boshi:boshi + CLAIM_PAGE]
    rows = [
        [InlineKeyboardButton(s[3][:60], callback_data=f"clpick:{s[0]}:{s[1]}:{s[2]}")]
        for s in chunk
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"claim:{page-1}"))
    if boshi + CLAIM_PAGE < len(slots):
        nav.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"claim:{page+1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


async def claim_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Xodim ro'yxatdan o'z ismini tanlaydi → Telegram ID avtomatik biriktiriladi."""
    query = update.callback_query
    user  = query.from_user
    remember_user(user)
    data  = query.data
    j     = load_jadval()

    if data.startswith("claim:"):
        page  = int(data.split(":")[1])
        slots = unclaimed_slots(j)
        if not slots:
            await query.answer()
            await query.edit_message_text(
                "✅ Hozircha bo'sh ism yo'q (yoki ro'yxat hali yuklanmagan).")
            return
        await query.answer()
        await query.edit_message_text(
            f"📝 Ro'yxatdan o'z ismingizni tanlang ({len(slots)} ta bo'sh):",
            reply_markup=claim_picker_kb(slots, page))
        return

    if data.startswith("clpick:"):
        _, gi, di, idx = data.split(":")
        gi, di, idx = int(gi), int(di), int(idx)
        kun = KUNLAR[di]
        lst = j["guruhlar"][gi]["kunlar"].get(kun, [])
        if not (0 <= idx < len(lst)):
            await query.answer("⚠️ Topilmadi, ro'yxat o'zgargan bo'lishi mumkin.", show_alert=True)
            return
        slot = lst[idx]
        if slot.get("id"):
            await query.answer("⚠️ Bu ism allaqachon band qilingan.", show_alert=True)
            return
        slot["id"] = user.id
        save_jadval(j)
        await query.answer("✅ Tanlandi!", show_alert=True)
        await query.edit_message_text(
            f"✅ Rahmat, {user.full_name}!\n"
            f"Siz «{slot['ism']}» sifatida ro'yxatga bog'landingiz.\n"
            f"({j['guruhlar'][gi]['nom']} — {kun})\n\n"
            f"Endi navbat e'lonida ismingiz bosilsa, akkauntingizga olib o'tadi.")
        return

    await query.answer()


# ── Admin boshqaruvi ──
async def boshqaruv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Faqat adminlar uchun.")
        return
    ctx.user_data.pop("kutilmoqda", None)
    await update.message.reply_text(
        "🛠 <b>Navbatchi boshqaruvi</b>\nKerakli amalni tanlang:",
        parse_mode="HTML",
        reply_markup=menu_keyboard(),
    )


async def boshqaruv_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Faqat adminlar uchun.", show_alert=True)
        return

    data = query.data
    j    = load_jadval()

    if data == "mng:home":
        ctx.user_data.pop("kutilmoqda", None)
        ctx.user_data.pop("kun_almash", None)
        await query.answer()
        await query.edit_message_text(
            "🛠 <b>Navbatchi boshqaruvi</b>\nKerakli amalni tanlang:",
            parse_mode="HTML", reply_markup=menu_keyboard())
        return

    if data == "mng:view":
        await query.answer()
        await query.edit_message_text(navbat_korinish_matni(), reply_markup=back_home_kb())
        return

    if data == "mng:swap":
        j["offset"] = j.get("offset", 0) + 1
        save_jadval(j)
        gi = aktiv_guruh_index(j)
        await query.answer("🔄 Hafta almashtirildi!", show_alert=True)
        await query.edit_message_text(
            f"🔄 Endi navbatchi: {j['guruhlar'][gi]['nom']}\n\n" + navbat_korinish_matni(),
            reply_markup=back_home_kb())
        return

    if data == "repl":
        await query.answer()
        await query.edit_message_text(
            "✏️ Qaysi haftada almashtiramiz / qo'shamiz?", reply_markup=repl_guruh_kb())
        return

    if data == "mnu:menu":
        await query.answer()
        await query.edit_message_text(
            "🍽 Qaysi kunning taomini o'zgartiramiz?", reply_markup=menu_kunlar_kb())
        return

    parts = data.split(":")
    tag   = parts[0]

    if tag == "mnu" and parts[1] == "day":
        wd  = int(parts[2])
        kun = KUNLAR[wd]
        ctx.user_data["kutilmoqda"] = {"amal": "ovqat", "wd": wd}
        eski = load_menu().get(wd, {}).get("name", "—")
        await query.answer()
        await query.edit_message_text(
            f"🍽 {kun} uchun hozirgi taom: <b>{html.escape(eski)}</b>\n\n"
            f"Yangi taom nomini yozib yuboring:",
            parse_mode="HTML")
        return

    if tag == "up":
        gi = int(parts[1])
        ctx.user_data["kutilmoqda"] = {"amal": "yuklash", "gi": gi}
        limit = PER_DAY * len(KUNLAR)
        await query.answer()
        await query.edit_message_text(
            f"📥 <b>{html.escape(j['guruhlar'][gi]['nom'])}</b> uchun xodimlar ro'yxatini yuboring.\n\n"
            f"• Har bir ism alohida qatorda (yoki vergul bilan).\n"
            f"• Ketma-ket har kunga {PER_DAY} tadan joylashtiriladi "
            f"(Dush–Shanba, jami {limit} ta).\n"
            f"• Botga shaxsiy xabar (lichka) qilib yuboring.\n\n"
            f"Bekor qilish: /boshqaruv ni qayta bosing.",
            parse_mode="HTML")
        return

    if tag == "rgg":
        gi = int(parts[1])
        await query.answer()
        await query.edit_message_text(
            f"✏️ {j['guruhlar'][gi]['nom']} — qaysi kun?", reply_markup=repl_kun_kb(gi))
        return

    if tag == "rgd":
        gi, di = int(parts[1]), int(parts[2])
        await query.answer()
        await query.edit_message_text(
            f"✏️ {j['guruhlar'][gi]['nom']} — {KUNLAR[di]}\n"
            f"Almashtiriladigan ismni tanlang (⏳ = ID bog'lanmagan), yoki yangi qo'shing:",
            reply_markup=repl_slot_kb(gi, di))
        return

    if tag == "rgp":
        gi, di, idx = int(parts[1]), int(parts[2]), int(parts[3])
        kun = KUNLAR[di]
        ctx.user_data["kutilmoqda"] = {"amal": "almashtirish", "gi": gi, "di": di, "idx": idx}
        await query.answer()
        if idx == -1:
            await query.edit_message_text(
                f"➕ {j['guruhlar'][gi]['nom']} — {kun}\n"
                f"Yangi xodim ismini (matn) yuboring (lichkada).")
        else:
            lst  = j["guruhlar"][gi]["kunlar"].get(kun, [])
            eski = lst[idx]["ism"] if 0 <= idx < len(lst) else "—"
            await query.edit_message_text(
                f"✏️ «{eski}» o'rniga yangi ismni (matn) yuboring (lichkada).\n"
                f"Uning ID si tozalanadi — yangi xodim /start bosib o'z ismini tanlaydi.")
        return

    await query.answer()


async def kun_almash_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kun almashtirish: bitta xodimni boshqa kunga ko'chirish yoki ikki xodimning
    kunini bir-biriga almashtirish — ID va ism birga ko'chadi, hech kim o'chmaydi."""
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Faqat adminlar uchun.", show_alert=True)
        return

    parts = query.data.split(":")   # da : step : mode : ...
    step  = parts[1]
    mode  = parts[2]
    j     = load_jadval()

    if step == "g":
        await query.answer()
        sarlavha = ("🔀 <b>Kun almashtirish</b>\nQaysi xodimni ko'chiramiz? "
                     "Avval hafta guruhini tanlang:") if mode == "src" else \
                    "🔀 Endi qaysi kunga ko'chiramiz? Hafta guruhini tanlang:"
        await query.edit_message_text(sarlavha, parse_mode="HTML", reply_markup=da_guruh_kb(mode))
        return

    if step == "d":
        gi = int(parts[3])
        await query.answer()
        await query.edit_message_text(
            f"🔀 {j['guruhlar'][gi]['nom']} — qaysi kun?",
            reply_markup=da_kun_kb(mode, gi))
        return

    if step == "s":
        gi, di = int(parts[3]), int(parts[4])
        await query.answer()
        matn = ("Ko'chiriladigan xodimni tanlang:" if mode == "src"
                else "Qaysi joyga qo'yamiz? (band joy tanlansa — ikkovi kunlarini almashtiradi)")
        await query.edit_message_text(
            f"🔀 {j['guruhlar'][gi]['nom']} — {KUNLAR[di]}\n{matn}",
            reply_markup=da_slot_kb(mode, gi, di))
        return

    if step == "pick":
        gi, di, idx = int(parts[3]), int(parts[4]), int(parts[5])
        kun = KUNLAR[di]

        if mode == "src":
            lst = j["guruhlar"][gi]["kunlar"].get(kun, [])
            if not (0 <= idx < len(lst)):
                await query.answer("⚠️ Topilmadi, ro'yxat o'zgargan bo'lishi mumkin.", show_alert=True)
                return
            ism = lst[idx]["ism"]
            ctx.user_data["kun_almash"] = {"gi": gi, "di": di, "idx": idx, "ism": ism}
            await query.answer(f"Tanlandi: {ism}")
            await query.edit_message_text(
                f"✅ Manba: «{ism}» ({j['guruhlar'][gi]['nom']} — {kun})\n\n"
                f"Endi qaysi kunga ko'chiramiz? Hafta guruhini tanlang:",
                reply_markup=da_guruh_kb("dst"))
            return

        # mode == "dst"
        src = ctx.user_data.get("kun_almash")
        if not src:
            await query.answer("⚠️ Avval manba xodimni tanlang.", show_alert=True)
            await query.edit_message_text(
                "🛠 <b>Navbatchi boshqaruvi</b>\nKerakli amalni tanlang:",
                parse_mode="HTML", reply_markup=menu_keyboard())
            return

        src_kun  = KUNLAR[src["di"]]
        src_list = j["guruhlar"][src["gi"]]["kunlar"].get(src_kun, [])
        if not (0 <= src["idx"] < len(src_list)):
            await query.answer("⚠️ Manba topilmadi, ro'yxat o'zgargan bo'lishi mumkin.", show_alert=True)
            ctx.user_data.pop("kun_almash", None)
            return
        src_entry = src_list[src["idx"]]

        if src["gi"] == gi and src["di"] == di and idx in (src["idx"], -1):
            await query.answer("⚠️ Bu allaqachon shu odamning joyi.", show_alert=True)
            return

        dst_list = j["guruhlar"][gi]["kunlar"].setdefault(kun, [])

        if idx == -1:
            src_list.pop(src["idx"])
            dst_list.append(src_entry)
            xabar = (f"✅ «{src_entry['ism']}» {j['guruhlar'][src['gi']]['nom']} {src_kun} dan "
                     f"{j['guruhlar'][gi]['nom']} {kun} kuniga ko'chirildi.\n"
                     f"ID saqlanib qoldi.")
        else:
            if not (0 <= idx < len(dst_list)):
                await query.answer("⚠️ Manzil topilmadi, ro'yxat o'zgargan bo'lishi mumkin.", show_alert=True)
                return
            dst_entry = dst_list[idx]
            if src["gi"] == gi and src["di"] == di:
                src_list[src["idx"]], src_list[idx] = src_list[idx], src_list[src["idx"]]
            else:
                src_list[src["idx"]], dst_list[idx] = dst_list[idx], src_list[src["idx"]]
            xabar = (f"✅ «{src_entry['ism']}» ({j['guruhlar'][src['gi']]['nom']} {src_kun}) ↔ "
                     f"«{dst_entry['ism']}» ({j['guruhlar'][gi]['nom']} {kun}) kunlari almashtirildi.\n"
                     f"Ikkalasining ID si saqlanib qoldi.")

        save_jadval(j)
        ctx.user_data.pop("kun_almash", None)
        await query.answer("✅ Bajarildi!", show_alert=True)
        await query.edit_message_text(xabar + "\n\n" + navbat_korinish_matni(), reply_markup=back_home_kb())
        return

    await query.answer()


async def admin_panel_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Vaqtinchalik adminlarni ko'rish/qo'shish — hamma admin ko'ra oladi,
    lekin faqat bosh admin (ADMIN_IDS) qo'sha/o'chira oladi."""
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Faqat adminlar uchun.", show_alert=True)
        return

    data = query.data

    if data == "adm:menu":
        await query.answer()
        vaqt = load_vaqt_adminlar()
        matn = "👤 <b>Vaqtinchalik adminlar</b>\n\n"
        matn += ("\n".join(f"• {info.get('name', uid)}" for uid, info in vaqt.items())
                 or "— hozircha yo'q —")
        await query.edit_message_text(matn, parse_mode="HTML", reply_markup=adm_menu_kb())
        return

    if data.startswith("adm:addpage:"):
        page = int(data.split(":")[2])
        await query.answer()
        await query.edit_message_text(
            "➕ Kimni vaqtinchalik admin qilamiz? Xodimlar ro'yxatidan tanlang:",
            reply_markup=adm_add_kb(page))
        return

    if data.startswith("adm:addpick:"):
        if not is_super_admin(query.from_user.id):
            await query.answer("⛔ Faqat bosh admin admin qo'sha oladi.", show_alert=True)
            return
        uid = data.split(":")[2]
        xodimlar = load_xodimlar()
        info = xodimlar.get(uid)
        if not info:
            await query.answer("⚠️ Topilmadi.", show_alert=True)
            return
        vaqt = load_vaqt_adminlar()
        vaqt[uid] = {"name": info.get("name", uid)}
        save_vaqt_adminlar(vaqt)
        await query.answer(f"✅ {info.get('name', uid)} admin qilindi!", show_alert=True)
        await query.edit_message_text(
            "👤 <b>Vaqtinchalik adminlar</b>\n\n"
            + "\n".join(f"• {v.get('name', u)}" for u, v in vaqt.items()),
            parse_mode="HTML", reply_markup=adm_menu_kb())
        return

    if data.startswith("adm:del:"):
        if not is_super_admin(query.from_user.id):
            await query.answer("⛔ Faqat bosh admin o'chira oladi.", show_alert=True)
            return
        uid  = data.split(":")[2]
        vaqt = load_vaqt_adminlar()
        nomi = vaqt.pop(uid, {}).get("name", uid)
        save_vaqt_adminlar(vaqt)
        await query.answer(f"❌ {nomi} adminlikdan olindi.", show_alert=True)
        matn = "👤 <b>Vaqtinchalik adminlar</b>\n\n"
        matn += ("\n".join(f"• {info.get('name', u)}" for u, info in vaqt.items())
                 or "— hozircha yo'q —")
        await query.edit_message_text(matn, parse_mode="HTML", reply_markup=adm_menu_kb())
        return

    await query.answer()


async def matn_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin yuborgan matnli ro'yxat / yangi ism (faqat tugma bosilgandan keyin)."""
    if not update.message or not update.message.text:
        return
    state = ctx.user_data.get("kutilmoqda")
    if not state:
        return
    user = update.effective_user
    if not is_admin(user.id):
        ctx.user_data.pop("kutilmoqda", None)
        return

    j    = load_jadval()
    amal = state.get("amal")
    text = update.message.text

    if amal == "yuklash":
        gi     = state["gi"]
        raw    = text.replace(",", "\n").splitlines()
        ismlar = [_clean_name(s) for s in raw]
        ismlar = [s for s in ismlar if s]
        ctx.user_data.pop("kutilmoqda", None)
        if not ismlar:
            await update.message.reply_text("⚠️ Hech qanday ism topilmadi. Qayta urinib ko'ring.")
            return
        placed, total = royxatni_joylashtir(j, gi, ismlar)
        save_jadval(j)
        limit = PER_DAY * len(KUNLAR)
        msg = (f"✅ {j['guruhlar'][gi]['nom']} ro'yxati yuklandi.\n"
               f"Qabul qilindi: {placed} ta (har kunga {PER_DAY} tadan).")
        if total > placed:
            msg += f"\n⚠️ {total - placed} ta ortiqcha ism ({limit} dan oshgani) joylashmadi."
        msg += ("\n\nEndi xodimlar botga /start bosib o'z ismlarini tanlasin.\n\n"
                + navbat_korinish_matni())
        await update.message.reply_text(msg)
        return

    if amal == "almashtirish":
        gi, di, idx = state["gi"], state["di"], state["idx"]
        kun       = KUNLAR[di]
        yangi_ism = text.strip()
        ctx.user_data.pop("kutilmoqda", None)
        if not yangi_ism:
            await update.message.reply_text("⚠️ Ism bo'sh. Qayta urinib ko'ring.")
            return
        lst = j["guruhlar"][gi]["kunlar"].setdefault(kun, [])
        if idx == -1:
            lst.append({"ism": yangi_ism, "id": None})
            save_jadval(j)
            await update.message.reply_text(
                f"✅ «{yangi_ism}» qo'shildi ({j['guruhlar'][gi]['nom']} — {kun}).\n"
                f"U /start bosib o'z ismini tanlasin.")
        elif 0 <= idx < len(lst):
            eski = lst[idx]["ism"]
            lst[idx] = {"ism": yangi_ism, "id": None}
            save_jadval(j)
            await update.message.reply_text(
                f"✅ «{eski}» → «{yangi_ism}» almashtirildi "
                f"({j['guruhlar'][gi]['nom']} — {kun}).\n"
                f"Yangi xodim /start bosib o'z ismini tanlasin.")
        else:
            await update.message.reply_text("⚠️ Slot topilmadi.")
        return

    if amal == "ovqat":
        wd        = state["wd"]
        kun       = KUNLAR[wd]
        yangi_nom = text.strip()
        ctx.user_data.pop("kutilmoqda", None)
        if not yangi_nom:
            await update.message.reply_text("⚠️ Taom nomi bo'sh. Qayta urinib ko'ring.")
            return
        menu = load_menu()
        eski = menu.get(wd, {}).get("name", "—")
        menu[wd] = {**menu.get(wd, {}), "name": yangi_nom}
        save_menu(menu)
        await update.message.reply_text(
            f"✅ {kun}: «{eski}» → «{yangi_nom}» ga o'zgartirildi.")
        return


# ══════════════════════════════════════════════════════
#  STARTUP — IKKALA JOB BIRLASHTIRILGAN
# ══════════════════════════════════════════════════════
async def on_startup(app: Application):
    from datetime import time as dtime

    # Navbatchi: har kuni 12:30
    async def navbat_job(context):
        await navbat_xabar_yuborish(app)

    app.job_queue.run_daily(
        navbat_job,
        time=dtime(NAVBAT_SOAT, NAVBAT_MINUT, 0, tzinfo=TIMEZONE),
    )

    # Ovqat so'rovi: har kuni 18:00
    async def survey_job(context):
        await send_daily_survey(app)

    app.job_queue.run_daily(
        survey_job,
        time=dtime(OPEN_HOUR, 0, 0, tzinfo=TIMEZONE),
    )

    # Ovoz yopilishi: har kuni CLOSE_HOUR (06:00) da natija ro'yxati
    async def close_job(context):
        await send_voting_results(app)

    app.job_queue.run_daily(
        close_job,
        time=dtime(CLOSE_HOUR, 0, 0, tzinfo=TIMEZONE),
    )

    # Haftalik ovqat hisoboti: Shanba 06:05 (oxirgi ovoz yopilgach).
    # Har kuni 06:05 da ishga tushadi, lekin faqat Shanba (weekday==5) da yuboradi —
    # bu PTB kun-indeksidagi noaniqlikdan qochish uchun ishonchli usul.
    async def weekly_job(context):
        if datetime.now(TIMEZONE).weekday() == 5:   # Shanba
            await send_weekly_food_report(app)

    app.job_queue.run_daily(
        weekly_job,
        time=dtime(CLOSE_HOUR, 5, 0, tzinfo=TIMEZONE),
    )

    logger.info(
        "✅ Bot ishga tushdi | Navbatchi: %02d:%02d | So'rov: %02d:00 | "
        "Yopilish: %02d:00 | Haftalik hisobot: Shanba %02d:05",
        NAVBAT_SOAT, NAVBAT_MINUT, OPEN_HOUR, CLOSE_HOUR, CLOSE_HOUR
    )


def main():
    # Ikkinchi nusxa ishga tushmasligi uchun avval qulfni olamiz
    acquire_single_instance_lock()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(on_startup)
        .build()
    )

    # Barcha ushlanmagan xatolar shu yerga keladi (Conflict, tarmoq, h.k.)
    app.add_error_handler(error_handler)

    # Navbatchi buyruqlari
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("royxat",     royxat))
    app.add_handler(CommandHandler("test",       test))
    app.add_handler(CommandHandler("boshqaruv",  boshqaruv))

    # Ovqat buyruqlari
    app.add_handler(CommandHandler("id",         get_id))
    app.add_handler(CommandHandler("surov",      surov))
    app.add_handler(CommandHandler("natija",     natija))
    app.add_handler(CommandHandler("bugun",      bugun_natija))
    app.add_handler(CommandHandler("kecha",      kecha_natija))
    app.add_handler(CommandHandler("statistika", statistika))

    # Inline tugmalar — navbatchi (boshqaruv + self-claim) ovqat tugmalaridan OLDIN
    app.add_handler(CallbackQueryHandler(
        claim_callback, pattern=r"^(claim|clpick):"))
    app.add_handler(CallbackQueryHandler(
        boshqaruv_callback, pattern=r"^(repl|mng:|up:|rgg:|rgd:|rgp:|mnu:)"))
    app.add_handler(CallbackQueryHandler(
        kun_almash_callback, pattern=r"^da:"))
    app.add_handler(CallbackQueryHandler(
        admin_panel_callback, pattern=r"^adm:"))
    # Inline tugmalar (ovqat)
    app.add_handler(CallbackQueryHandler(button))

    # Admin matnli kiritishi (ro'yxat yuklash / yangi ism) — faqat state bo'lsa ishlaydi
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, matn_handler))

    print("=" * 60)
    print("✅  Birlashtirilgan bot ishga tushdi!")
    print(f"    Guruh ID    : {CHAT_ID}")
    print(f"    Topik ID    : {MESSAGE_THREAD_ID}")
    print(f"    Adminlar    : {ADMIN_IDS}")
    print(f"    {NAVBAT_SOAT:02d}:{NAVBAT_MINUT:02d} — Navbatchilar e'lon qilinadi")
    print(f"    {OPEN_HOUR:02d}:00 — Ertangi ovqat so'rovi yuboriladi")
    print(f"    {CLOSE_HOUR:02d}:00 — Ovqat javobi qabul qilish tugaydi")
    print(f"    {CLOSE_HOUR:02d}:05 — Shanba kuni haftalik hisobot")
    print("    Buyruqlar:")
    print("      /start       — xodim ro'yxatga kiradi")
    print("      /royxat      — barcha xodimlar + ID lari")
    print("      /boshqaruv   — navbatchi jadvalini boshqarish (admin, tugmali)")
    print("      /test        — navbatchi xabarini hozir yuborish")
    print("      /surov       — ovqat so'rovini hozir yuborish")
    print("      /bugun       — bugungi ovqat natijasi")
    print("      /kecha       — kechagi ovqat natijasi (ism bilan)")
    print("      /natija      — bugungi natija ro'yxatini guruhga yuborish")
    print("      /statistika  — haftalik ovqat statistikasi")
    print("      /id          — chat va user ID larini ko'rish")
    print("=" * 60)

    app.run_polling()


if __name__ == "__main__":
    main()
