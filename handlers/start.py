# handlers/start.py
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from keyboards.user_kb import main_menu, support_menu, join_menu, back_to_main
from utils.helpers import check_membership
import config

router = Router()


async def send_stored_file(bot: Bot, chat_id: int, file_code: str):
    """ارسال فایل ذخیره‌شده به کاربر با کپی از کانال ذخیره."""
    f = await db.get_file(file_code)
    if not f:
        await bot.send_message(chat_id, "❌ فایل مورد نظر یافت نشد یا حذف شده است.")
        return
    try:
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=f["storage_chat_id"],
            message_id=f["storage_message_id"],
        )
    except Exception:
        # تلاش پشتیبان: ارسال مستقیم با file_id
        await _send_by_file_id(bot, chat_id, f)


async def _send_by_file_id(bot: Bot, chat_id: int, f):
    ftype = f["file_type"]
    fid = f["file_id"]
    cap = f["caption"] or None
    try:
        if ftype == "document":
            await bot.send_document(chat_id, fid, caption=cap)
        elif ftype == "photo":
            await bot.send_photo(chat_id, fid, caption=cap)
        elif ftype == "video":
            await bot.send_video(chat_id, fid, caption=cap)
        elif ftype == "audio":
            await bot.send_audio(chat_id, fid, caption=cap)
        elif ftype == "voice":
            await bot.send_voice(chat_id, fid, caption=cap)
        elif ftype == "animation":
            await bot.send_animation(chat_id, fid, caption=cap)
        else:
            await bot.send_document(chat_id, fid, caption=cap)
    except Exception:
        await bot.send_message(chat_id, "❌ خطا در ارسال فایل. لطفاً بعداً تلاش کنید.")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    await state.clear()
    user = message.from_user
    await db.add_user(user.id, user.username or "", user.first_name or "")

    payload = command.args  # کد فایل در صورت وجود

    # اگر عضویت اجباری فعال است، بررسی شود
    if await db.is_force_join():
        not_joined = await check_membership(bot, user.id)
        if not_joined:
            # کد فایل را برای پس از عضویت ذخیره می‌کنیم
            await state.update_data(pending_file=payload)
            text = "📢 برای استفاده از ربات ابتدا در کانال‌های زیر عضو شوید:\n\n"
            for ch in not_joined:
                text += f"🔹 {ch['title']}\n"
            await message.answer(text, reply_markup=join_menu(not_joined))
            return

    if payload:
        await send_stored_file(bot, message.chat.id, payload)
        await message.answer(
            f"🤖 به ربات «{config.BOT_NAME}» خوش آمدید.",
            reply_markup=main_menu(),
        )
        return

    await message.answer(
        f"🤖 سلام {user.first_name}!\n"
        f"به ربات «{config.BOT_NAME}» خوش آمدید.\n\n"
        f"از منوی زیر استفاده کنید:",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery, state: FSMContext, bot: Bot):
    not_joined = await check_membership(bot, call.from_user.id)
    if not_joined:
        text = "❌ ابتدا در تمامی کانال‌های الزامی عضو شوید.\n\n"
        text += "کانال‌های باقی‌مانده:\n"
        for ch in not_joined:
            text += f"🔹 {ch['title']}\n"
        await call.message.edit_text(text, reply_markup=join_menu(not_joined))
        await call.answer("هنوز عضو همه کانال‌ها نشده‌اید.", show_alert=True)
        return

    await call.answer("✅ عضویت شما تأیید شد.", show_alert=True)
    data = await state.get_data()
    pending = data.get("pending_file")
    await state.clear()

    try:
        await call.message.delete()
    except Exception:
        pass

    if pending:
        await send_stored_file(bot, call.from_user.id, pending)

    await bot.send_message(
        call.from_user.id,
        f"🤖 به ربات «{config.BOT_NAME}» خوش آمدید.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "user_getfile")
async def user_getfile(call: CallbackQuery):
    await call.message.edit_text(
        "📥 برای دریافت فایل، روی لینک اختصاصی فایل کلیک کنید.\n"
        "لینک‌ها توسط مدیریت ربات منتشر می‌شوند.",
        reply_markup=back_to_main(),
    )
    await call.answer()


@router.callback_query(F.data == "user_support")
async def user_support(call: CallbackQuery):
    await call.message.edit_text(
        f"📞 پشتیبانی ربات «{config.BOT_NAME}»\n\n"
        f"برای ارتباط با پشتیبانی از دکمه زیر استفاده کنید:\n"
        f"👤 {config.OWNER_USERNAME}",
        reply_markup=support_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "user_back_main")
async def user_back_main(call: CallbackQuery):
    await call.message.edit_text(
        f"🤖 منوی اصلی ربات «{config.BOT_NAME}»",
        reply_markup=main_menu(),
    )
    await call.answer()
