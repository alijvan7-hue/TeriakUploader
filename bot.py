import os, secrets, logging, sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ─── تنظیمات ────────────────────────────────────────────────
TOKEN        = os.getenv("BOT_TOKEN",        "8176940583:AAE9LZKyrBiK4nZk_pHeRGL6icKhYlPPS24")
OWNER_ID     = int(os.getenv("OWNER_ID",    "1375809015"))
CHANNEL_USER = os.getenv("CHANNEL_USERNAME","@teriak18")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.WARNING)
logger = logging.getLogger(__name__)

# ─── دیتابیس ────────────────────────────────────────────────
_conn = None
def db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect("bot.db", check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
    return _conn

def init_db():
    c = db().cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
            joined_at TEXT, is_banned INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY, file_name TEXT, file_type TEXT,
            caption TEXT, uploaded_by INTEGER, uploaded_at TEXT, share_token TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY, username TEXT, added_by INTEGER, added_at TEXT
        );
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY, channel_username TEXT, channel_title TEXT, added_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        INSERT OR IGNORE INTO settings VALUES ('force_join','1');
    """)
    # اضافه کردن ستون channel_title اگه وجود نداشت (برای آپگرید دیتابیس قدیمی)
    try:
        db().execute("ALTER TABLE channels ADD COLUMN channel_title TEXT DEFAULT ''")
        db().commit()
    except Exception:
        pass
    db().commit()

# ─── cache کوچک برای is_admin ────────────────────────────────
_admin_cache: set = set()
_admin_cache_time = 0

def refresh_admin_cache():
    global _admin_cache, _admin_cache_time
    rows = db().execute("SELECT user_id FROM admins").fetchall()
    _admin_cache = {r[0] for r in rows}
    _admin_cache_time = datetime.now().timestamp()

def is_admin(uid):
    if uid == OWNER_ID: return True
    if datetime.now().timestamp() - _admin_cache_time > 60:
        refresh_admin_cache()
    return uid in _admin_cache

def is_banned(uid):
    r = db().execute("SELECT is_banned FROM users WHERE user_id=?", (uid,)).fetchone()
    return r and r[0] == 1

def register_user(user):
    db().execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,0)",
                 (user.id, user.username or "", user.full_name, datetime.now().isoformat()))
    db().commit()

def get_setting(key):
    r = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else ""

def set_setting(key, value):
    db().execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
    db().commit()

def get_channels():
    return db().execute("SELECT channel_id, channel_username, channel_title FROM channels").fetchall()

def get_stats():
    c = db().cursor()
    total  = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = c.execute("SELECT COUNT(*) FROM users WHERE is_banned=0").fetchone()[0]
    banned = c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
    files  = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    admins = c.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    chans  = c.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    return total, active, banned, files, admins, chans

def get_all_admin_ids():
    rows = db().execute("SELECT user_id FROM admins").fetchall()
    return [OWNER_ID] + [r[0] for r in rows]

# ─── عضویت اجباری (چند کانال) با نمایش دقیق کدوم جوین ندادی ──
async def check_member_detailed(context, uid):
    """
    برگردونه: (all_joined: bool, not_joined: list of (cid, uname, title))
    """
    if get_setting("force_join") != "1":
        return True, []
    channels = get_channels()
    if not channels:
        return True, []
    not_joined = []
    for (cid, uname, title) in channels:
        try:
            m = await context.bot.get_chat_member(cid, uid)
            if m.status not in ("member", "administrator", "creator"):
                not_joined.append((cid, uname, title))
        except Exception:
            not_joined.append((cid, uname, title))
    return len(not_joined) == 0, not_joined

async def check_member(context, uid) -> bool:
    ok, _ = await check_member_detailed(context, uid)
    return ok

async def send_join_msg(update, context, not_joined=None):
    """
    اگه not_joined پاس بشه، فقط اون کانال‌ها رو نشون بده.
    وگرنه همه کانال‌ها رو نشون بده.
    """
    if not_joined is None:
        channels = get_channels()
        not_joined = [(cid, uname, title) for cid, uname, title in channels]

    buttons = []
    for (_, uname, title) in not_joined:
        ch = uname.lstrip("@")
        display = title if title else uname
        buttons.append([InlineKeyboardButton(f"📢 {display}", url=f"https://t.me/{ch}")])

    buttons.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])

    ch_list = "\n".join(
        f"• <b>{(title if title else uname)}</b> ({uname})" for _, uname, title in not_joined
    )
    text = (
        "⛔️ <b>دسترسی محدود شده</b>\n\n"
        "برای استفاده از <b>اپلودر تریاک</b> باید در کانال‌های زیر عضو بشی:\n\n"
        f"{ch_list}\n\n"
        "بعد از عضویت روی دکمه پایین بزن 👇"
    )
    await update.effective_message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
    )

# ─── کیبوردها ───────────────────────────────────────────────
def kb_main(adm=False):
    if adm:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ پنل مدیریت", callback_data="admin_panel")],
            [InlineKeyboardButton("📨 تیکت پشتیبانی", callback_data="support_ticket")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 ارسال تیکت پشتیبانی", callback_data="support_ticket")],
    ])

def kb_admin():
    fj = "✅" if get_setting("force_join") == "1" else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 آمار",         callback_data="admin_stats"),
         InlineKeyboardButton("📢 همگانی",       callback_data="admin_broadcast")],
        [InlineKeyboardButton("📤 آپلود فایل",  callback_data="admin_upload"),
         InlineKeyboardButton("📋 لیست فایل‌ها", callback_data="admin_filelist_0")],
        [InlineKeyboardButton("🔍 جستجوی فایل", callback_data="admin_search"),
         InlineKeyboardButton("💾 بک‌آپ",        callback_data="admin_backup")],
        [InlineKeyboardButton("🚫 بن/آن‌بن",    callback_data="admin_ban"),
         InlineKeyboardButton("📋 لیست بن",     callback_data="admin_banlist_0")],
        [InlineKeyboardButton("👮 ادمین‌ها",     callback_data="admin_admins"),
         InlineKeyboardButton("📡 کانال‌ها",     callback_data="admin_channels")],
        [InlineKeyboardButton(f"🔒 عضویت اجباری: {fj}", callback_data="admin_forcejoin")],
        [InlineKeyboardButton("🔙 برگشت",        callback_data="main_menu")],
    ])

def kb_back(target="admin_panel"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data=target)]])

# ─── /start ─────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    if is_banned(user.id):
        await update.message.reply_text("🚫 حساب شما مسدود شده است.")
        return
    if context.args:
        arg = context.args[0]
        if arg.startswith("file_"):
            ok, not_joined = await check_member_detailed(context, user.id)
            if not ok:
                context.user_data["pending_file"] = arg[5:]
                await send_join_msg(update, context, not_joined)
                return
            await deliver_file(update, context, arg[5:])
            return
    ok, not_joined = await check_member_detailed(context, user.id)
    if not ok:
        await send_join_msg(update, context, not_joined)
        return
    adm  = is_admin(user.id)
    name = user.first_name
    if adm:
        text = f"👑 <b>خوش اومدی، {name} عزیز!</b>\n\n🔧 پنل مدیریت <b>اپلودر تریاک</b> در اختیارته 👇"
    else:
        text = f"🌿 <b>سلام {name} عزیز!</b>\n\nبه <b>اپلودر تریاک</b> خوش اومدی 🖤\n\nاگه سوالی داری تیکت بفرست 👇"
    await update.message.reply_text(text, reply_markup=kb_main(adm), parse_mode=ParseMode.HTML)

# ─── ارسال فایل ─────────────────────────────────────────────
async def deliver_file(update, context, token):
    row = db().execute(
        "SELECT file_id,file_name,file_type,caption FROM files WHERE share_token=?", (token,)
    ).fetchone()
    if not row:
        await update.effective_message.reply_text("❌ این فایل وجود نداره یا حذف شده.")
        return
    fid, fname, ftype, cap = row
    cap = cap or fname or "فایل"
    msg = update.effective_message
    try:
        fn = {
            "photo":     msg.reply_photo,
            "video":     msg.reply_video,
            "audio":     msg.reply_audio,
            "voice":     msg.reply_voice,
            "animation": msg.reply_animation,
        }.get(ftype, msg.reply_document)
        await fn(fid, caption=cap)
    except Exception as e:
        await msg.reply_text(f"❌ خطا: {e}")

# ─── صفحه‌بندی فایل‌ها ──────────────────────────────────────
PAGE_SIZE = 5

async def show_file_list(query, page=0):
    rows = db().execute(
        "SELECT file_name,file_type,share_token,uploaded_at FROM files ORDER BY uploaded_at DESC LIMIT ? OFFSET ?",
        (PAGE_SIZE, page * PAGE_SIZE)
    ).fetchall()
    total = db().execute("SELECT COUNT(*) FROM files").fetchone()[0]
    if not rows:
        await query.message.edit_text("📂 هیچ فایلی آپلود نشده.", reply_markup=kb_back())
        return
    binfo = await query.get_bot().get_me()
    text  = f"📋 <b>لیست فایل‌ها</b>  (صفحه {page+1})\n\n"
    btns  = []
    emoji_map = {"photo":"🖼","video":"🎬","audio":"🎵","voice":"🎙","animation":"🎞","document":"📄"}
    for name, ftype, token, date in rows:
        link = f"https://t.me/{binfo.username}?start=file_{token}"
        text += f"{emoji_map.get(ftype,'📄')} <b>{name}</b>\n📅 {date[:10]} | <a href='{link}'>لینک</a>\n\n"
        btns.append([InlineKeyboardButton(f"🗑 {name[:28]}", callback_data=f"del_{token}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"admin_filelist_{page-1}"))
    if (page+1)*PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"admin_filelist_{page+1}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")])
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns),
                                   disable_web_page_preview=True)

async def show_ban_list(query, page=0):
    rows = db().execute(
        "SELECT user_id,username,full_name FROM users WHERE is_banned=1 LIMIT ? OFFSET ?",
        (PAGE_SIZE, page * PAGE_SIZE)
    ).fetchall()
    total = db().execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
    if not rows:
        await query.message.edit_text("✅ هیچ کاربری بن نشده.", reply_markup=kb_back())
        return
    text = f"🚫 <b>لیست بن‌شده‌ها</b>  (صفحه {page+1}  |  کل: {total})\n\n"
    btns = []
    for uid, uname, fname in rows:
        un = f"@{uname}" if uname else "—"
        text += f"👤 <b>{fname}</b>  {un}\n🆔 <code>{uid}</code>\n\n"
        btns.append([InlineKeyboardButton(f"✅ آن‌بن: {fname[:20]}", callback_data=f"unban_{uid}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"admin_banlist_{page-1}"))
    if (page+1)*PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"admin_banlist_{page+1}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")])
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

async def show_channels_panel(q):
    rows = get_channels()
    text = "📡 <b>کانال‌های عضویت اجباری</b>\n\n"
    btns = []
    if rows:
        for cid, uname, title in rows:
            display = title if title else uname
            text += f"• <b>{display}</b>  {uname}  (<code>{cid}</code>)\n"
            btns.append([InlineKeyboardButton(f"🗑 حذف {display[:20]}", callback_data=f"delch_{cid}")])
    else:
        text += "هیچ کانالی اضافه نشده.\n"
    btns.append([InlineKeyboardButton("➕ اضافه کردن کانال", callback_data="admin_addchannel")])
    btns.append([InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")])
    await q.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

async def show_admins_panel(q):
    rows = db().execute("SELECT user_id,username,added_at FROM admins").fetchall()
    text = "👮 <b>لیست ادمین‌ها</b>\n\n"
    btns = []
    for uid, uname, added_at in rows:
        un = f"@{uname}" if uname else "بدون یوزرنیم"
        text += f"• <code>{uid}</code>  {un}  ({added_at[:10]})\n"
        btns.append([InlineKeyboardButton(f"🗑 حذف {un[:20]}", callback_data=f"deladmin_{uid}")])
    if not rows:
        text += "هیچ ادمینی نیست.\n"
    text += "\n➕ برای اضافه کردن ادمین جدید، آیدی و یوزرنیم رو بفرست:\n<code>addadmin آیدی یوزرنیم</code>"
    btns.append([InlineKeyboardButton("➕ اضافه کردن ادمین", callback_data="admin_addadmin")])
    btns.append([InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")])
    await q.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

# ─── callback handler ────────────────────────────────────────
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    data = q.data
    user = q.from_user

    if is_banned(user.id):
        await q.answer("🚫 حساب شما مسدود است.", show_alert=True)
        return

    # ── عضویت ──
    if data == "check_join":
        ok, not_joined = await check_member_detailed(context, user.id)
        if ok:
            pending = context.user_data.pop("pending_file", None)
            if pending:
                await deliver_file(update, context, pending)
                return
            adm  = is_admin(user.id)
            name = user.first_name
            text = f"✅ <b>تأیید شد!</b>\n\n{'👑 خوش اومدی به پنل مدیریت!' if adm else f'🌿 سلام {name}، خوش اومدی 🖤'}"
            await q.message.edit_text(text, reply_markup=kb_main(adm), parse_mode=ParseMode.HTML)
        else:
            # نشون بده کدوم کانال‌ها رو هنوز جوین نداده
            ch_names = ", ".join(
                (title if title else uname) for _, uname, title in not_joined
            )
            await q.answer(
                f"❌ هنوز در این کانال‌ها عضو نشدی:\n{ch_names}",
                show_alert=True
            )
            # آپدیت کن دکمه‌ها فقط کانال‌های نجوین‌شده رو نشون بده
            buttons = []
            for (_, uname, title) in not_joined:
                ch = uname.lstrip("@")
                display = title if title else uname
                buttons.append([InlineKeyboardButton(f"📢 {display}", url=f"https://t.me/{ch}")])
            buttons.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")])
            ch_list = "\n".join(
                f"• <b>{(title if title else uname)}</b> ({uname})" for _, uname, title in not_joined
            )
            text = (
                "⛔️ <b>هنوز عضو نشدی!</b>\n\n"
                "این کانال‌ها رو هنوز جوین ندادی:\n\n"
                f"{ch_list}\n\n"
                "بعد از عضویت دوباره بررسی کن 👇"
            )
            try:
                await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
            except Exception:
                pass
        return

    # ── منو ──
    if data == "main_menu":
        adm = is_admin(user.id)
        await q.message.edit_text(
            "🌿 <b>اپلودر تریاک</b>",
            reply_markup=kb_main(adm), parse_mode=ParseMode.HTML)
        return

    # ── تیکت پشتیبانی ──
    if data == "support_ticket":
        context.user_data["state"] = "support_msg"
        await q.message.edit_text(
            "📨 <b>تیکت پشتیبانی</b>\n\nپیامت رو بفرست (هر نوع محتوایی).\nبرای لغو /cancel بزن",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="main_menu")]]))
        return

    # ── پاسخ ادمین ──
    if data.startswith("reply_"):
        target_uid = int(data[6:])
        context.user_data["state"]    = "admin_reply"
        context.user_data["reply_to"] = target_uid
        await q.message.reply_text(
            f"✍️ پاسخ به کاربر <code>{target_uid}</code> رو بفرست:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]))
        return

    # ── بن از تیکت (فقط اونر) ──
    if data.startswith("tban_"):
        if user.id != OWNER_ID:
            await q.answer("⛔ فقط اونر می‌تونه بن کنه!", show_alert=True)
            return
        target_uid = int(data[5:])
        db().execute("UPDATE users SET is_banned=1 WHERE user_id=?", (target_uid,))
        db().commit()
        await q.answer(f"🚫 کاربر {target_uid} بن شد.", show_alert=True)
        await q.message.edit_reply_markup(reply_markup=None)
        return

    # ── آن‌بن از لیست ──
    if data.startswith("unban_"):
        if not is_admin(user.id):
            await q.answer("⛔ دسترسی ندارید!", show_alert=True)
            return
        uid = int(data[6:])
        db().execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
        db().commit()
        await q.answer("✅ آن‌بن شد!", show_alert=True)
        page = int(context.user_data.get("banlist_page", 0))
        await show_ban_list(q, page)
        return

    # ── حذف ادمین ──
    if data.startswith("deladmin_"):
        if user.id != OWNER_ID:
            await q.answer("⛔ فقط اونر!", show_alert=True); return
        did = int(data[9:])
        db().execute("DELETE FROM admins WHERE user_id=?", (did,))
        db().commit()
        refresh_admin_cache()
        await q.answer("✅ ادمین حذف شد!", show_alert=True)
        await show_admins_panel(q)
        return

    # ── حذف فایل ──
    if data.startswith("del_"):
        if not is_admin(user.id):
            await q.answer("⛔ دسترسی ندارید!", show_alert=True)
            return
        token = data[4:]
        db().execute("DELETE FROM files WHERE share_token=?", (token,))
        db().commit()
        await q.answer("✅ فایل حذف شد!", show_alert=True)
        await q.message.edit_text("⚙️ <b>پنل مدیریت</b>", reply_markup=kb_admin(), parse_mode=ParseMode.HTML)
        return

    # ── صفحه‌بندی ──
    if data.startswith("admin_filelist_"):
        if not is_admin(user.id):
            await q.answer("⛔", show_alert=True); return
        page = int(data[15:])
        await show_file_list(q, page)
        return

    if data.startswith("admin_banlist_"):
        if not is_admin(user.id):
            await q.answer("⛔", show_alert=True); return
        page = int(data[14:])
        context.user_data["banlist_page"] = page
        await show_ban_list(q, page)
        return

    # ── حذف کانال ──
    if data.startswith("delch_"):
        if user.id != OWNER_ID:
            await q.answer("⛔ فقط اونر!", show_alert=True); return
        cid = int(data[6:])
        db().execute("DELETE FROM channels WHERE channel_id=?", (cid,))
        db().commit()
        await q.answer("✅ کانال حذف شد!", show_alert=True)
        await show_channels_panel(q)
        return

    # ── پنل ادمین ──
    if not is_admin(user.id) and data.startswith("admin_"):
        await q.answer("⛔ دسترسی ندارید!", show_alert=True)
        return

    if data == "admin_panel":
        await q.message.edit_text("⚙️ <b>پنل مدیریت اپلودر تریاک</b>",
                                   reply_markup=kb_admin(), parse_mode=ParseMode.HTML)

    elif data == "admin_stats":
        total, active, banned, files, admins, chans = get_stats()
        fj = "✅ فعال" if get_setting("force_join") == "1" else "❌ غیرفعال"
        text = (
            f"📊 <b>آمار اپلودر تریاک</b>\n{'─'*24}\n"
            f"👥 کل کاربران:    <b>{total}</b>\n"
            f"✅ فعال:           <b>{active}</b>\n"
            f"🚫 بن‌شده:         <b>{banned}</b>\n"
            f"📁 فایل‌ها:        <b>{files}</b>\n"
            f"👮 ادمین‌ها:       <b>{admins}</b>\n"
            f"📡 کانال‌ها:       <b>{chans}</b>\n"
            f"🔒 عضویت اجباری:  <b>{fj}</b>\n"
            f"{'─'*24}\n🕐 {datetime.now().strftime('%Y/%m/%d  %H:%M')}"
        )
        await q.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_back())

    elif data == "admin_broadcast":
        context.user_data["state"] = "broadcast"
        await q.message.edit_text(
            "📢 <b>پیام همگانی</b>\n\nپیام رو بفرست:\n\nبرای لغو /cancel بزن",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]))

    elif data == "admin_upload":
        context.user_data["state"] = "upload_file"
        await q.message.edit_text(
            "📤 <b>آپلود فایل</b>\n\nفایل رو بفرست (هر فرمتی):\n\nبرای لغو /cancel بزن",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]))

    elif data == "admin_search":
        context.user_data["state"] = "search_file"
        await q.message.edit_text(
            "🔍 <b>جستجوی فایل</b>\n\nنام فایل رو بنویس:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]))

    elif data == "admin_backup":
        try:
            import shutil
            shutil.copy2("bot.db", "backup_temp.db")
            with open("backup_temp.db", "rb") as f:
                await context.bot.send_document(
                    OWNER_ID, document=f,
                    filename=f"taryak_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    caption="💾 بک‌آپ دیتابیس اپلودر تریاک")
            os.remove("backup_temp.db")
            await q.answer("✅ بک‌آپ ارسال شد!", show_alert=True)
        except Exception as e:
            await q.answer(f"❌ {e}", show_alert=True)

    elif data == "admin_ban":
        context.user_data["state"] = "ban_user"
        own = " (فقط اونر می‌تونه ادمین بن کنه)" if user.id != OWNER_ID else ""
        await q.message.edit_text(
            f"🚫 <b>بن کاربر</b>{own}\n\n"
            "آیدی عددی کاربر رو بنویس:\n"
            "مثال: <code>123456789</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]))

    elif data == "admin_admins":
        if user.id != OWNER_ID:
            await q.answer("⛔ فقط اونر!", show_alert=True); return
        await show_admins_panel(q)

    elif data == "admin_addadmin":
        if user.id != OWNER_ID:
            await q.answer("⛔ فقط اونر!", show_alert=True); return
        context.user_data["state"] = "add_admin"
        await q.message.edit_text(
            "👮 <b>اضافه کردن ادمین جدید</b>\n\n"
            "آیدی عددی و یوزرنیم ادمین رو بفرست:\n"
            "<code>addadmin آیدی یوزرنیم</code>\n\n"
            "مثال: <code>addadmin 123456789 ali</code>\n\n"
            "برای لغو /cancel بزن",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_admins")]]))

    elif data == "admin_channels":
        if user.id != OWNER_ID:
            await q.answer("⛔ فقط اونر!", show_alert=True); return
        await show_channels_panel(q)

    elif data == "admin_forcejoin":
        new = "0" if get_setting("force_join") == "1" else "1"
        set_setting("force_join", new)
        st = "✅ فعال" if new == "1" else "❌ غیرفعال"
        await q.answer(f"عضویت اجباری {st} شد!", show_alert=True)
        await q.message.edit_text("⚙️ <b>پنل مدیریت اپلودر تریاک</b>",
                                   reply_markup=kb_admin(), parse_mode=ParseMode.HTML)

    elif data == "admin_addchannel":
        if user.id != OWNER_ID:
            await q.answer("⛔", show_alert=True); return
        context.user_data["state"] = "add_channel"
        await q.message.edit_text(
            "📡 <b>اضافه کردن کانال</b>\n\n"
            "ربات رو ادمین کانال کن، بعد آیدی عددی یا یوزرنیم کانال رو بفرست:\n"
            "مثال: <code>@mychannel</code> یا <code>-1001234567890</code>\n\n"
            "برای لغو /cancel بزن",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="admin_channels")]]))

# ─── message handler ─────────────────────────────────────────
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg  = update.message
    if not msg: return
    register_user(user)
    if is_banned(user.id):
        await msg.reply_text("🚫 حساب شما مسدود شده است.")
        return
    if msg.text and msg.text == "/cancel":
        context.user_data.pop("state", None)
        await msg.reply_text("❌ لغو شد.", reply_markup=kb_main(is_admin(user.id)))
        return

    state = context.user_data.get("state")

    # ── تیکت پشتیبانی ──
    if state == "support_msg":
        admins = get_all_admin_ids()
        uname  = f"@{user.username}" if user.username else "—"
        header = (
            f"📨 <b>تیکت جدید</b>\n{'─'*22}\n"
            f"👤 <b>{user.full_name}</b>  {uname}\n"
            f"🆔 <code>{user.id}</code>\n{'─'*22}"
        )
        for aid in admins:
            try:
                await context.bot.send_message(aid, header, parse_mode=ParseMode.HTML)
                await msg.copy(aid)
                btns = [[InlineKeyboardButton("✍️ پاسخ", callback_data=f"reply_{user.id}")]]
                if aid == OWNER_ID:
                    btns.append([InlineKeyboardButton("🚫 بن کاربر", callback_data=f"tban_{user.id}")])
                await context.bot.send_message(aid, "─" * 14, reply_markup=InlineKeyboardMarkup(btns))
            except Exception as e:
                logger.warning(f"ticket to {aid}: {e}")
        context.user_data.pop("state", None)
        await msg.reply_text("✅ <b>تیکت ارسال شد!</b>\n\nیه ادمین جواب میده 🖤",
                              parse_mode=ParseMode.HTML, reply_markup=kb_main(is_admin(user.id)))
        return

    # ── پاسخ ادمین ──
    if state == "admin_reply" and is_admin(user.id):
        target = context.user_data.pop("reply_to", None)
        context.user_data.pop("state", None)
        if target:
            try:
                await context.bot.send_message(target,
                    "📩 <b>پاسخ پشتیبانی اپلودر تریاک:</b>\n" + "─"*22, parse_mode=ParseMode.HTML)
                await msg.copy(target)
                await msg.reply_text("✅ پاسخ ارسال شد.", reply_markup=kb_admin())
            except Exception as e:
                await msg.reply_text(f"❌ خطا: {e}")
        return

    # ── آپلود فایل ──
    if state == "upload_file" and is_admin(user.id):
        file_id = file_name = None; file_type = "document"
        if msg.document:    file_id,file_name,file_type = msg.document.file_id, msg.document.file_name or "document","document"
        elif msg.photo:     file_id,file_name,file_type = msg.photo[-1].file_id,"photo","photo"
        elif msg.video:     file_id,file_name,file_type = msg.video.file_id, msg.video.file_name or "video","video"
        elif msg.audio:     file_id,file_name,file_type = msg.audio.file_id, msg.audio.file_name or "audio","audio"
        elif msg.voice:     file_id,file_name,file_type = msg.voice.file_id,"voice","voice"
        elif msg.animation: file_id,file_name,file_type = msg.animation.file_id,"animation","animation"
        if file_id:
            token = secrets.token_urlsafe(12)
            db().execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?)",
                         (file_id, file_name, file_type, msg.caption or "", user.id,
                          datetime.now().isoformat(), token))
            db().commit()
            binfo = await context.bot.get_me()
            link  = f"https://t.me/{binfo.username}?start=file_{token}"
            context.user_data.pop("state", None)
            await msg.reply_text(
                f"✅ <b>آپلود شد!</b>\n\n📁 <code>{file_name}</code>\n🔑 <code>{token}</code>\n\n🔗 {link}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📤 آپلود فایل بعدی", callback_data="admin_upload")],
                    [InlineKeyboardButton("🗑 حذف همین فایل", callback_data=f"del_{token}")],
                    [InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")]]))
        else:
            await msg.reply_text("❌ فایل شناسایی نشد.")
        return

    # ── همگانی ──
    if state == "broadcast" and is_admin(user.id):
        ulist = db().execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
        sent = failed = 0
        sm = await msg.reply_text("⏳ در حال ارسال...")
        for (uid,) in ulist:
            try: await msg.copy(uid); sent += 1
            except: failed += 1
        context.user_data.pop("state", None)
        await sm.edit_text(f"📢 <b>تموم شد</b>\n\n✅ {sent}\n❌ {failed}",
                            parse_mode=ParseMode.HTML, reply_markup=kb_back())
        return

    # ── جستجوی فایل ──
    if state == "search_file" and is_admin(user.id) and msg.text:
        q_text = msg.text.strip()
        rows = db().execute(
            "SELECT file_name,file_type,share_token,uploaded_at FROM files WHERE file_name LIKE ?",
            (f"%{q_text}%",)).fetchall()
        if not rows:
            await msg.reply_text("❌ پیدا نشد.", reply_markup=kb_back()); return
        binfo = await context.bot.get_me()
        text  = f"🔍 <b>نتایج «{q_text}»:</b>\n\n"
        btns  = []
        emap  = {"photo":"🖼","video":"🎬","audio":"🎵","voice":"🎙","animation":"🎞"}
        for name, ftype, token, date in rows[:10]:
            link = f"https://t.me/{binfo.username}?start=file_{token}"
            text += f"{emap.get(ftype,'📄')} <b>{name}</b>  {date[:10]}\n<a href='{link}'>لینک</a>\n\n"
            btns.append([InlineKeyboardButton(f"🗑 {name[:28]}", callback_data=f"del_{token}")])
        btns.append([InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")])
        context.user_data.pop("state", None)
        await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns),
                              disable_web_page_preview=True)
        return

    # ── بن کاربر ──
    if state == "ban_user" and is_admin(user.id) and msg.text:
        uid_s = msg.text.strip()
        try:
            uid = int(uid_s)
        except ValueError:
            await msg.reply_text("❌ آیدی عددی وارد کن."); return
        if is_admin(uid) and user.id != OWNER_ID:
            await msg.reply_text("⛔ فقط اونر می‌تونه ادمین بن کنه!")
            context.user_data.pop("state", None); return
        db().execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        db().commit()
        await msg.reply_text(f"🚫 کاربر <code>{uid}</code> بن شد.", parse_mode=ParseMode.HTML,
                              reply_markup=kb_back())
        context.user_data.pop("state", None)
        return

    # ── اضافه کردن ادمین (فقط اونر) ──
    if state == "add_admin" and user.id == OWNER_ID and msg.text:
        parts = msg.text.strip().split()
        cmd = parts[0].lower()
        if cmd == "addadmin" and len(parts) >= 2:
            try:
                nid   = int(parts[1])
                uname = parts[2].lstrip("@") if len(parts) > 2 else ""
                db().execute("INSERT OR REPLACE INTO admins VALUES (?,?,?,?)",
                             (nid, uname, user.id, datetime.now().isoformat()))
                db().commit()
                refresh_admin_cache()
                # پیام تبریک به ادمین جدید
                bot_info = await context.bot.get_me()
                congrats_text = (
                    f"🎉 <b>تبریک!</b>\n\n"
                    f"شما به لیست ادمین‌های <b>اپلودر تریاک</b> اضافه شدید 🖤\n\n"
                    f"✅ حالا می‌تونید از این امکانات استفاده کنید:\n"
                    f"• 📤 آپلود و مدیریت فایل‌ها\n"
                    f"• 📢 ارسال پیام همگانی\n"
                    f"• 🚫 بن/آن‌بن کاربران\n"
                    f"• 📨 پاسخ به تیکت‌های پشتیبانی\n"
                    f"• 📊 مشاهده آمار ربات\n\n"
                    f"برای شروع /start بزن 👇"
                )
                try:
                    await context.bot.send_message(nid, congrats_text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass  # ممکنه ادمین هنوز ربات رو استارت نزده باشه
                un_display = f"@{uname}" if uname else str(nid)
                # برگشت به پنل ادمین‌ها بدون رفتن صفحه اول
                rows = db().execute("SELECT user_id,username,added_at FROM admins").fetchall()
                text_panel = "👮 <b>لیست ادمین‌ها</b>\n\n"
                btns = []
                for r_uid, r_uname, r_added in rows:
                    r_un = f"@{r_uname}" if r_uname else "بدون یوزرنیم"
                    text_panel += f"• <code>{r_uid}</code>  {r_un}  ({r_added[:10]})\n"
                    btns.append([InlineKeyboardButton(f"🗑 حذف {r_un[:20]}", callback_data=f"deladmin_{r_uid}")])
                text_panel += f"\n✅ ادمین <b>{un_display}</b> با موفقیت اضافه شد!\n\n"
                text_panel += "➕ برای اضافه کردن ادمین دیگه:\n<code>addadmin آیدی یوزرنیم</code>"
                btns.append([InlineKeyboardButton("➕ اضافه کردن ادمین دیگه", callback_data="admin_addadmin")])
                btns.append([InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")])
                context.user_data.pop("state", None)
                await msg.reply_text(text_panel, parse_mode=ParseMode.HTML,
                                     reply_markup=InlineKeyboardMarkup(btns))
            except ValueError:
                await msg.reply_text("❌ آیدی اشتباهه.")
        else:
            await msg.reply_text("❌ فرمت اشتباه.\nمثال: <code>addadmin 123456789 ali</code>",
                                  parse_mode=ParseMode.HTML)
        return

    # ── اضافه کردن کانال (فقط اونر) ──
    if state == "add_channel" and user.id == OWNER_ID and msg.text:
        inp = msg.text.strip()
        try:
            chat = await context.bot.get_chat(inp)
            title = chat.title or ""
            uname_ch = f"@{chat.username}" if chat.username else inp
            db().execute("INSERT OR REPLACE INTO channels VALUES (?,?,?,?)",
                         (chat.id, uname_ch, title, datetime.now().isoformat()))
            db().commit()
            context.user_data.pop("state", None)
            # برگشت به پنل کانال‌ها (نه صفحه اول)
            rows = get_channels()
            text_panel = "📡 <b>کانال‌های عضویت اجباری</b>\n\n"
            btns = []
            for cid, un, ch_title in rows:
                display = ch_title if ch_title else un
                text_panel += f"• <b>{display}</b>  {un}  (<code>{cid}</code>)\n"
                btns.append([InlineKeyboardButton(f"🗑 حذف {display[:20]}", callback_data=f"delch_{cid}")])
            text_panel += f"\n✅ کانال <b>{title or uname_ch}</b> با موفقیت اضافه شد!\n"
            text_panel += "⚠️ مطمئن شو ربات ادمین اون کانال باشه."
            btns.append([InlineKeyboardButton("➕ اضافه کردن کانال دیگه", callback_data="admin_addchannel")])
            btns.append([InlineKeyboardButton("🔙 پنل", callback_data="admin_panel")])
            await msg.reply_text(text_panel, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(btns))
        except Exception as e:
            await msg.reply_text(f"❌ خطا: {e}\n\nمطمئن شو ربات ادمین کانال هست.")
        return

    # ── پیش‌فرض ──
    ok, not_joined = await check_member_detailed(context, user.id)
    if not ok:
        await send_join_msg(update, context, not_joined); return
    await msg.reply_text("از منوی زیر انتخاب کن 👇", reply_markup=kb_main(is_admin(user.id)))

# ─── اجرا ───────────────────────────────────────────────────
def main():
    init_db()
    refresh_admin_cache()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    logger.warning("🌿 اپلودر تریاک آنلاین شد...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
