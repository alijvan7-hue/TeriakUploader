# middlewares/ban.py
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery

from database.db import db
import config


class BanMiddleware(BaseMiddleware):
    """جلوگیری از استفاده کاربران بن‌شده. مالک هرگز بن نمی‌شود."""

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user

        if user and user.id != config.OWNER_ID:
            if await db.is_banned(user.id):
                text = "🚫 شما توسط مدیریت مسدود شده‌اید."
                if event.message:
                    await event.message.answer(text)
                elif event.callback_query:
                    await event.callback_query.answer(text, show_alert=True)
                return  # پردازش متوقف می‌شود

        return await handler(event, data)
