# handlers/admin.py
import os
import asyncio

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from database.db import db
from states.states import (
    UploadFile, SearchFile, Broadcast, AddAdmin, RemoveAdmin,
    BanUser, UnbanUser, UserInfo, AddChannel, RemoveChannel, AdminReply,
)
from keyboards.admin_kb import (
    admin_main, cancel_back, back_main_only, admins_menu, users_menu,
    channels_menu, files_list_kb, file_actions_kb, confirm_delete_kb,
    support_msg_actions_kb, support_list_kb,
)
from utils.helpers import generate_code, human_size, format_date, build_file_link
import config

router = Router()
PER_PAGE = 5


async def is_panel_user(user_id: int) -> bool:
    return await db.is_admin(user_id)


# ---------- ورود به پنل ----------
@router.message(Command("panel"))
@router.message(Command("admin"))
async def open_panel(message: Message, state: FSMContext):
    if not await is_panel_user(message.from_user.id):
        await message.answer("⛔️ شما دسترسی به پنل مدیریت ندارید.")
        return
    await state.clear()
    await message.answer(
        f"⚙️ پنل مدیریت ربات «{config.BOT_NAME}»\n\nیک گزینه را انتخاب کنید:",
        reply_markup=admin_main(),
    )


@router.callback_query(F.data == "adm_back_main")
async def adm_back_main(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        f"⚙️ پنل مدیریت ربات «{config.BOT_NAME}»\n\nیک گزینه را انتخاب کنید:",
        reply_markup=admin_main(),
    )
    await call.answer()


@router.callback_query(F.data == "adm_cancel")
async def adm_cancel(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text("❌ عملیات لغو شد.", reply_markup=admin_main())
    await call.answer("لغو شد.")


# ---------- وضعیت ----------
@router.callback_query(F.data == "adm_status")
async def adm_status(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    users = await db.count_users()
    files = await db.count_files()
    admins = await db.count_admins()
    banned = await db.count_banned()
    support_total = await db.count_support_messages("all")
    support_today = await db.count_support_messages("today")
    force = "🟢 فعال" if await db.is_force_join() else "🔴 غیرفعال"
    text = (
        "📊 وضعیت ربات\n\n"
        f"👥 تعداد کاربران: {users}\n"
        f"📂 تعداد فایل‌ها: {files}\n"
        f"🛡 تعداد ادمین‌ها: {admins}\n"
        f"🚫 کاربران بن‌شده: {banned}\n"
        f"💬 پیام‌های پشتیبانی: {support_total} (امروز: {support_today})\n"
        f"📢 عضویت اجباری: {force}"
    )
    await call.message.edit_text(text, reply_markup=back_main_only())
    await call.answer()


# ---------- پیام‌های پشتیبانی ----------
@router.callback_query(F.data == "adm_support_msgs")
async def adm_support_msgs(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await _show_support_page(call, "all", 0)


@router.callback_query(F.data == "sup_noop")
async def sup_noop(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data.startswith("sup_filter:"))
async def sup_filter(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    parts = call.data.split(":")
    filter_type = parts[1]
    page = int(parts[2])
    await _show_support_page(call, filter_type, page)


async def _show_support_page(call: CallbackQuery, filter_type: str, page: int):
    total = await db.count_support_messages(filter_type)
    msgs = await db.get_support_messages(filter_type, limit=PER_PAGE, offset=page * PER_PAGE)

    filter_labels = {"today": "امروز", "week": "هفته اخیر", "all": "همه"}
    label = filter_labels.get(filter_type, "همه")

    if not msgs:
        text = f"💬 پیام‌های پشتیبانی — {label}\n\n❌ پیامی یافت نشد."
    else:
        text = f"💬 پیام‌های پشتیبانی — {label}\n📊 تعداد کل: {total}\n\n"
        text += "─" * 25 + "\n"
        for m in msgs:
            uname = f"@{m['username']}" if m["username"] else "—"
            text += (
                f"👤 {m['first_name']} | {uname}\n"
                f"🆔 {m['user_id']}\n"
                f"📅 {format_date(m['sent_at'])}\n"
                f"💬 {m['message_text'][:200]}\n"
                f"─" * 25 + "\n"
            )

    # اگر پیام خیلی بلند شد تقسیم کن
    if len(text) > 4000:
        text = text[:4000] + "\n..."

    await call.message.edit_text(
        text,
        reply_markup=support_list_kb(filter_type, page, total, PER_PAGE),
    )
    await call.answer()


# ---------- پاسخ ادمین به کاربر ----------
@router.callback_query(F.data.startswith("sup_reply:"))
async def sup_reply(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    await state.set_state(AdminReply.waiting_reply)
    await state.update_data(reply_to_user=user_id)
    await call.message.answer(
        f"✏️ پاسخ خود را برای کاربر {user_id} بنویسید:\n(متن، عکس، ویدیو و ... قبول می‌شود)",
        reply_markup=cancel_back(),
    )
    await call.answer()


@router.message(AdminReply.waiting_reply)
async def admin_reply_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data.get("reply_to_user")
    await state.clear()

    try:
        await bot.send_message(target_user_id, "📬 پاسخ پشتیبانی:")
        await bot.copy_message(
            chat_id=target_user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer("✅ پاسخ با موفقیت ارسال شد.", reply_markup=back_main_only())
    except Exception:
        await message.answer("❌ ارسال پاسخ ناموفق بود. کاربر ربات را بلاک کرده یا آیدی اشتباه است.",
                             reply_markup=back_main_only())


# ---------- بن از پنل پشتیبانی ----------
@router.callback_query(F.data.startswith("sup_ban:"))
async def sup_ban(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    if user_id == config.OWNER_ID:
        await call.answer("⛔️ مالک قابل بن نیست.", show_alert=True)
        return
    await db.ban_user(user_id)
    await call.answer(f"🚫 کاربر {user_id} بن شد.", show_alert=True)


# ---------- اطلاعات کاربر از پنل پشتیبانی ----------
@router.callback_query(F.data.startswith("sup_info:"))
async def sup_info(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db.get_user(user_id)
    if not user:
        await call.answer("کاربری یافت نشد.", show_alert=True)
        return
    status = "🚫 بن شده" if user["is_banned"] else "✅ فعال"
    uname = f"@{user['username']}" if user["username"] else "—"
    text = (
        f"ℹ️ اطلاعات کاربر\n\n"
        f"🆔 آیدی: {user['user_id']}\n"
        f"👤 نام: {user['first_name'] or '—'}\n"
        f"🔖 یوزرنیم: {uname}\n"
        f"📅 عضویت: {format_date(user['joined_at'])}\n"
        f"وضعیت: {status}"
    )
    await call.answer(text, show_alert=True)


# ---------- آپلود فایل ----------
@router.callback_query(F.data == "adm_upload")
async def adm_upload(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(UploadFile.waiting_file)
    await call.message.edit_text(
        "📤 فایل مورد نظر را ارسال کنید.",
        reply_markup=cancel_back(),
    )
    await call.answer()


@router.message(UploadFile.waiting_file)
async def upload_receive(message: Message, state: FSMContext, bot: Bot):
    file_type = file_id = file_name = None
    file_size = 0

    if message.document:
        file_type, file_id = "document", message.document.file_id
        file_name = message.document.file_name or "document"
        file_size = message.document.file_size or 0
    elif message.photo:
        file_type, file_id = "photo", message.photo[-1].file_id
        file_name = "photo.jpg"
        file_size = message.photo[-1].file_size or 0
    elif message.video:
        file_type, file_id = "video", message.video.file_id
        file_name = message.video.file_name or "video.mp4"
        file_size = message.video.file_size or 0
    elif message.audio:
        file_type, file_id = "audio", message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
        file_size = message.audio.file_size or 0
    elif message.voice:
        file_type, file_id = "voice", message.voice.file_id
        file_name = "voice.ogg"
        file_size = message.voice.file_size or 0
    elif message.animation:
        file_type, file_id = "animation", message.animation.file_id
        file_name = message.animation.file_name or "animation.gif"
        file_size = message.animation.file_size or 0
    else:
        await message.answer("❌ نوع فایل پشتیبانی نمی‌شود.", reply_markup=cancel_back())
        return

    try:
        stored = await bot.copy_message(
            chat_id=config.STORAGE_CHANNEL_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception:
        await message.answer("❌ ذخیره در کانال ذخیره ناموفق بود.", reply_markup=back_main_only())
        await state.clear()
        return

    code = generate_code()
    while await db.get_file(code):
        code = generate_code()

    await db.add_file(code, file_id, file_type, file_name, file_size,
                      message.caption or "", config.STORAGE_CHANNEL_ID, stored.message_id)

    link = await build_file_link(bot, code)
    await state.clear()
    await message.answer(
        f"✅ فایل آپلود شد.\n\n📄 نام: {file_name}\n📦 حجم: {human_size(file_size)}\n🔗 لینک:\n{link}",
        reply_markup=back_main_only(),
    )


# ---------- مدیریت فایل‌ها ----------
@router.callback_query(F.data == "adm_files")
async def adm_files(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    files = await db.list_files(limit=50)
    if not files:
        await call.message.edit_text("📂 هیچ فایلی ثبت نشده است.", reply_markup=back_main_only())
        await call.answer()
        return
    await call.message.edit_text("📂 لیست فایل‌ها:", reply_markup=files_list_kb(files))
    await call.answer()


@router.callback_query(F.data.startswith("file_view:"))
async def file_view(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    f = await db.get_file(code)
    if not f:
        await call.answer("فایل یافت نشد.", show_alert=True)
        return
    text = f"📄 {f['file_name']}\n📦 {human_size(f['file_size'])}\n📅 {format_date(f['created_at'])}"
    await call.message.edit_text(text, reply_markup=file_actions_kb(code))
    await call.answer()


@router.callback_query(F.data.startswith("file_link:"))
async def file_link(call: CallbackQuery, bot: Bot):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    f = await db.get_file(code)
    if not f:
        await call.answer("فایل یافت نشد.", show_alert=True)
        return
    link = await build_file_link(bot, code)
    await call.message.edit_text(f"📎 لینک فایل:\n\n{link}", reply_markup=file_actions_kb(code))
    await call.answer()


@router.callback_query(F.data.startswith("file_info:"))
async def file_info(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    f = await db.get_file(code)
    if not f:
        await call.answer("فایل یافت نشد.", show_alert=True)
        return
    text = (
        f"🆔 کد: {f['file_code']}\n📄 نام: {f['file_name']}\n"
        f"📦 حجم: {human_size(f['file_size'])}\n🗂 نوع: {f['file_type']}\n"
        f"📝 کپشن: {f['caption'] or '—'}\n📅 تاریخ: {format_date(f['created_at'])}"
    )
    await call.message.edit_text(text, reply_markup=file_actions_kb(code))
    await call.answer()


@router.callback_query(F.data.startswith("file_del:"))
async def file_del(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    await call.message.edit_text("🗑 آیا مطمئن هستید؟", reply_markup=confirm_delete_kb(code))
    await call.answer()


@router.callback_query(F.data.startswith("file_delyes:"))
async def file_delyes(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    code = call.data.split(":", 1)[1]
    await db.delete_file(code)
    await call.message.edit_text("✅ فایل حذف شد.", reply_markup=back_main_only())
    await call.answer("حذف شد.")


# ---------- جستجوی فایل ----------
@router.callback_query(F.data == "adm_search")
async def adm_search(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(SearchFile.waiting_query)
    await call.message.edit_text("🔍 عبارت جستجو را وارد کنید:", reply_markup=cancel_back())
    await call.answer()


@router.message(SearchFile.waiting_query)
async def search_receive(message: Message, state: FSMContext):
    query = message.text.strip()
    files = await db.search_files(query)
    await state.clear()
    if not files:
        await message.answer("🔍 نتیجه‌ای یافت نشد.", reply_markup=back_main_only())
        return
    await message.answer(f"🔍 {len(files)} نتیجه:", reply_markup=files_list_kb(files))


# ---------- پیام همگانی ----------
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(Broadcast.waiting_message)
    await call.message.edit_text("📢 پیام همگانی را ارسال کنید:", reply_markup=cancel_back())
    await call.answer()


@router.message(Broadcast.waiting_message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = await db.get_all_user_ids()
    success = failed = 0
    status = await message.answer("⏳ در حال ارسال...")
    for uid in user_ids:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"📢 ارسال شد.\n✅ موفق: {success}\n❌ ناموفق: {failed}", reply_markup=back_main_only())


# ---------- مدیریت ادمین‌ها ----------
@router.callback_query(F.data == "adm_admins")
async def adm_admins(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text("👥 مدیریت ادمین‌ها", reply_markup=admins_menu())
    await call.answer()


@router.callback_query(F.data == "adm_add_admin")
async def adm_add_admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != config.OWNER_ID:
        await call.answer("⛔️ فقط مالک.", show_alert=True)
        return
    await state.set_state(AddAdmin.waiting_id)
    await call.message.edit_text("➕ آیدی عددی کاربر را ارسال کنید:", reply_markup=cancel_back())
    await call.answer()


@router.message(AddAdmin.waiting_id)
async def add_admin_receive(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("❌ آیدی نامعتبر.", reply_markup=cancel_back())
        return
    uid = int(text)
    user = await db.get_user(uid)
    await db.add_admin(uid, user["username"] if user else "")
    await state.clear()
    await message.answer(f"✅ کاربر {uid} ادمین شد.", reply_markup=back_main_only())


@router.callback_query(F.data == "adm_remove_admin")
async def adm_remove_admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != config.OWNER_ID:
        await call.answer("⛔️ فقط مالک.", show_alert=True)
        return
    await state.set_state(RemoveAdmin.waiting_id)
    await call.message.edit_text("➖ آیدی ادمین برای حذف:", reply_markup=cancel_back())
    await call.answer()


@router.message(RemoveAdmin.waiting_id)
async def remove_admin_receive(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("❌ آیدی نامعتبر.", reply_markup=cancel_back())
        return
    uid = int(text)
    if uid == config.OWNER_ID:
        await message.answer("⛔️ مالک قابل حذف نیست.", reply_markup=cancel_back())
        return
    await db.remove_admin(uid)
    await state.clear()
    await message.answer(f"✅ ادمین {uid} حذف شد.", reply_markup=back_main_only())


@router.callback_query(F.data == "adm_list_admins")
async def adm_list_admins(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    admins = await db.get_admins()
    text = f"📋 ادمین‌ها\n\n👑 مالک: {config.OWNER_ID} ({config.OWNER_USERNAME})\n"
    for a in admins:
        uname = f"@{a['username']}" if a["username"] else "—"
        text += f"🛡 {a['user_id']} ({uname})\n"
    await call.message.edit_text(text, reply_markup=back_main_only())
    await call.answer()


# ---------- مدیریت کاربران ----------
@router.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text("🚫 مدیریت کاربران", reply_markup=users_menu())
    await call.answer()


@router.callback_query(F.data == "adm_ban")
async def adm_ban(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(BanUser.waiting_id)
    await call.message.edit_text("🚫 آیدی کاربر برای بن:", reply_markup=cancel_back())
    await call.answer()


@router.message(BanUser.waiting_id)
async def ban_receive(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("❌ آیدی نامعتبر.", reply_markup=cancel_back())
        return
    uid = int(text)
    if uid == config.OWNER_ID:
        await message.answer("⛔️ مالک قابل بن نیست.", reply_markup=cancel_back())
        return
    await db.ban_user(uid)
    await state.clear()
    await message.answer(f"🚫 کاربر {uid} بن شد.", reply_markup=back_main_only())


@router.callback_query(F.data == "adm_unban")
async def adm_unban(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(UnbanUser.waiting_id)
    await call.message.edit_text("✅ آیدی کاربر برای آن‌بن:", reply_markup=cancel_back())
    await call.answer()


@router.message(UnbanUser.waiting_id)
async def unban_receive(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("❌ آیدی نامعتبر.", reply_markup=cancel_back())
        return
    uid = int(text)
    await db.unban_user(uid)
    await state.clear()
    await message.answer(f"✅ کاربر {uid} آن‌بن شد.", reply_markup=back_main_only())


@router.callback_query(F.data == "adm_userinfo")
async def adm_userinfo(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(UserInfo.waiting_id)
    await call.message.edit_text("ℹ️ آیدی کاربر را ارسال کنید:", reply_markup=cancel_back())
    await call.answer()


@router.message(UserInfo.waiting_id)
async def userinfo_receive(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("❌ آیدی نامعتبر.", reply_markup=cancel_back())
        return
    uid = int(text)
    user = await db.get_user(uid)
    await state.clear()
    if not user:
        await message.answer("❌ کاربری یافت نشد.", reply_markup=back_main_only())
        return
    status = "🚫 بن" if user["is_banned"] else "✅ فعال"
    uname = f"@{user['username']}" if user["username"] else "—"
    await message.answer(
        f"🆔 {user['user_id']}\n👤 {user['first_name'] or '—'}\n🔖 {uname}\n📅 {format_date(user['joined_at'])}\n{status}",
        reply_markup=back_main_only(),
    )


# ---------- کانال‌ها ----------
@router.callback_query(F.data == "adm_channels")
async def adm_channels(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    force = await db.is_force_join()
    await call.message.edit_text("📢 مدیریت عضویت اجباری", reply_markup=channels_menu(force))
    await call.answer()


@router.callback_query(F.data == "adm_toggle_join")
async def adm_toggle_join(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    current = await db.is_force_join()
    await db.set_setting("force_join", "0" if current else "1")
    force = not current
    await call.message.edit_text(
        f"✅ عضویت اجباری {'فعال' if force else 'غیرفعال'} شد.",
        reply_markup=channels_menu(force),
    )
    await call.answer()


@router.callback_query(F.data == "adm_add_channel")
async def adm_add_channel(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AddChannel.waiting_channel)
    await call.message.edit_text("➕ آیدی یا یوزرنیم کانال را ارسال کنید:", reply_markup=cancel_back())
    await call.answer()


@router.message(AddChannel.waiting_channel)
async def add_channel_receive(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip()
    try:
        chat = await bot.get_chat(text)
    except Exception:
        await message.answer("❌ کانال یافت نشد.", reply_markup=cancel_back())
        return
    invite_link = ""
    try:
        invite_link = await bot.export_chat_invite_link(chat.id)
    except Exception:
        invite_link = chat.invite_link or ""
    await db.add_channel(chat.id, chat.title or "کانال", chat.username or "", invite_link)
    await state.clear()
    await message.answer(f"✅ کانال «{chat.title}» اضافه شد.", reply_markup=back_main_only())


@router.callback_query(F.data == "adm_remove_channel")
async def adm_remove_channel(call: CallbackQuery, state: FSMContext):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    channels = await db.get_channels()
    if not channels:
        await call.message.edit_text("❌ کانالی ثبت نشده.", reply_markup=back_main_only())
        await call.answer()
        return
    await state.set_state(RemoveChannel.waiting_channel)
    text = "➖ آیدی کانال برای حذف:\n\n"
    for ch in channels:
        text += f"🔹 {ch['title']} — `{ch['channel_id']}`\n"
    await call.message.edit_text(text, reply_markup=cancel_back(), parse_mode="Markdown")
    await call.answer()


@router.message(RemoveChannel.waiting_channel)
async def remove_channel_receive(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("❌ آیدی نامعتبر.", reply_markup=cancel_back())
        return
    await db.remove_channel(int(text))
    await state.clear()
    await message.answer(f"✅ کانال حذف شد.", reply_markup=back_main_only())


@router.callback_query(F.data == "adm_list_channels")
async def adm_list_channels(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    channels = await db.get_channels()
    if not channels:
        await call.message.edit_text("📋 کانالی ثبت نشده.", reply_markup=back_main_only())
        await call.answer()
        return
    text = "📋 کانال‌ها:\n\n"
    for ch in channels:
        uname = f"@{ch['username']}" if ch["username"] else "—"
        text += f"🔹 {ch['title']} | {uname} | {ch['channel_id']}\n"
    await call.message.edit_text(text, reply_markup=back_main_only())
    await call.answer()


# ---------- بکاپ ----------
@router.callback_query(F.data == "adm_backup")
async def adm_backup(call: CallbackQuery, bot: Bot):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await call.answer("در حال آماده‌سازی...")
    if not os.path.exists(config.DB_PATH):
        await call.message.answer("❌ فایل دیتابیس یافت نشد.")
        return
    doc = FSInputFile(config.DB_PATH, filename="backup.db")
    await bot.send_document(call.from_user.id, doc, caption="💾 بکاپ دیتابیس")
    await call.message.answer("✅ بکاپ ارسال شد.", reply_markup=back_main_only())


# ---------- تنظیمات ----------
@router.callback_query(F.data == "adm_settings")
async def adm_settings(call: CallbackQuery):
    if not await is_panel_user(call.from_user.id):
        await call.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    force = "🟢 فعال" if await db.is_force_join() else "🔴 غیرفعال"
    text = (
        f"⚙️ تنظیمات\n\n"
        f"🤖 نام: {config.BOT_NAME}\n"
        f"👑 مالک: {config.OWNER_USERNAME}\n"
        f"📦 کانال ذخیره: {config.STORAGE_CHANNEL_ID}\n"
        f"📢 عضویت اجباری: {force}"
    )
    await call.message.edit_text(text, reply_markup=back_main_only())
    await call.answer()
