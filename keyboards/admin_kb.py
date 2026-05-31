# keyboards/admin_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 بررسی وضعیت", callback_data="adm_status")
    kb.button(text="📢 پیام همگانی", callback_data="adm_broadcast")
    kb.button(text="📂 مدیریت فایل‌ها", callback_data="adm_files")
    kb.button(text="📤 آپلود فایل", callback_data="adm_upload")
    kb.button(text="🔍 جستجوی فایل", callback_data="adm_search")
    kb.button(text="👥 مدیریت ادمین‌ها", callback_data="adm_admins")
    kb.button(text="🚫 مدیریت کاربران", callback_data="adm_users")
    kb.button(text="📢 عضویت اجباری", callback_data="adm_channels")
    kb.button(text="💾 دریافت بکاپ", callback_data="adm_backup")
    kb.button(text="⚙️ تنظیمات", callback_data="adm_settings")
    kb.adjust(2)
    return kb.as_markup()


def cancel_back() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت", callback_data="adm_back_main")
    kb.button(text="❌ لغو عملیات", callback_data="adm_cancel")
    kb.adjust(2)
    return kb.as_markup()


def back_main_only() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت", callback_data="adm_back_main")
    return kb.as_markup()


def admins_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ افزودن ادمین", callback_data="adm_add_admin")
    kb.button(text="➖ حذف ادمین", callback_data="adm_remove_admin")
    kb.button(text="📋 لیست ادمین‌ها", callback_data="adm_list_admins")
    kb.button(text="🔙 بازگشت", callback_data="adm_back_main")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def users_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 بن کاربر", callback_data="adm_ban")
    kb.button(text="✅ آن‌بن کاربر", callback_data="adm_unban")
    kb.button(text="ℹ️ اطلاعات کاربر", callback_data="adm_userinfo")
    kb.button(text="🔙 بازگشت", callback_data="adm_back_main")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def channels_menu(force_join: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ افزودن کانال", callback_data="adm_add_channel")
    kb.button(text="➖ حذف کانال", callback_data="adm_remove_channel")
    kb.button(text="📋 لیست کانال‌ها", callback_data="adm_list_channels")
    toggle = "🔴 غیرفعال کردن" if force_join else "🟢 فعال کردن"
    kb.button(text=f"عضویت اجباری: {toggle}", callback_data="adm_toggle_join")
    kb.button(text="🔙 بازگشت", callback_data="adm_back_main")
    kb.adjust(2, 1, 1, 1)
    return kb.as_markup()


def files_list_kb(files) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f in files:
        name = f["file_name"] or f["file_code"]
        kb.button(text=f"📄 {name}", callback_data=f"file_view:{f['file_code']}")
    kb.button(text="🔙 بازگشت", callback_data="adm_back_main")
    kb.adjust(1)
    return kb.as_markup()


def file_actions_kb(file_code: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📎 مشاهده لینک", callback_data=f"file_link:{file_code}")
    kb.button(text="ℹ️ اطلاعات فایل", callback_data=f"file_info:{file_code}")
    kb.button(text="🗑 حذف فایل", callback_data=f"file_del:{file_code}")
    kb.button(text="🔙 بازگشت", callback_data="adm_files")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def confirm_delete_kb(file_code: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ بله، حذف کن", callback_data=f"file_delyes:{file_code}")
    kb.button(text="❌ خیر", callback_data=f"file_view:{file_code}")
    kb.adjust(2)
    return kb.as_markup()
