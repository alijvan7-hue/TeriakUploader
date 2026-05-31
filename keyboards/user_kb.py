# keyboards/user_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 دریافت فایل", callback_data="user_getfile")
    kb.button(text="📞 تماس با پشتیبانی", callback_data="user_support")
    kb.adjust(1)
    return kb.as_markup()


def support_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    username = config.OWNER_USERNAME.lstrip("@")
    kb.button(text="✉️ ارتباط با پشتیبانی", url=f"https://t.me/{username}")
    kb.button(text="🔙 بازگشت", callback_data="user_back_main")
    kb.adjust(1)
    return kb.as_markup()


def join_menu(channels, joined_button: bool = True) -> InlineKeyboardMarkup:
    """ساخت کیبورد عضویت اجباری از روی کانال‌های باقی‌مانده."""
    kb = InlineKeyboardBuilder()
    for ch in channels:
        title = ch["title"] or "کانال"
        if ch["username"]:
            url = f"https://t.me/{ch['username'].lstrip('@')}"
        elif ch["invite_link"]:
            url = ch["invite_link"]
        else:
            url = f"https://t.me/c/{str(ch['channel_id']).replace('-100', '')}"
        kb.button(text=f"🔹 {title}", url=url)
    kb.adjust(1)
    if joined_button:
        kb.row(InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_join"))
    return kb.as_markup()


def back_to_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 بازگشت", callback_data="user_back_main")
    return kb.as_markup()
