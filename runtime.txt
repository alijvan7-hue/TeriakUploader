# utils/helpers.py
import secrets
import string
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from database.db import db


def generate_code(length: int = 10) -> str:
    """تولید کد یکتا برای فایل."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def human_size(size: int) -> str:
    """تبدیل بایت به فرمت خوانا."""
    if not size:
        return "نامشخص"
    units = ["B", "KB", "MB", "GB", "TB"]
    s = float(size)
    for unit in units:
        if s < 1024:
            return f"{s:.2f} {unit}"
        s /= 1024
    return f"{s:.2f} PB"


def format_date(timestamp: int) -> str:
    if not timestamp:
        return "نامشخص"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


async def get_bot_username(bot: Bot) -> str:
    import config

    if config.BOT_USERNAME:
        return config.BOT_USERNAME.lstrip("@")
    me = await bot.get_me()
    config.BOT_USERNAME = me.username
    return me.username


async def build_file_link(bot: Bot, file_code: str) -> str:
    username = await get_bot_username(bot)
    return f"https://t.me/{username}?start={file_code}"


async def check_membership(bot: Bot, user_id: int) -> list:
    """بررسی عضویت کاربر در همه کانال‌ها.
    لیست کانال‌هایی را که کاربر هنوز عضو نشده برمی‌گرداند."""
    not_joined = []
    channels = await db.get_channels()
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
        except (TelegramBadRequest, TelegramForbiddenError):
            # اگر ربات نتواند وضعیت را بررسی کند، کانال را نادیده می‌گیریم
            continue
        except Exception:
            continue
    return not_joined
