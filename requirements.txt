# bot.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.db import db
from middlewares.ban import BanMiddleware
from handlers import start, user, admin

logging.basicConfig(level=logging.INFO)


async def main():
    await db.connect()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # میدلور بن (روی پیام‌ها و کالبک‌ها)
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())

    # ثبت روترها
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(user.router)

    # کش کردن یوزرنیم ربات
    me = await bot.get_me()
    if not config.BOT_USERNAME:
        config.BOT_USERNAME = me.username
    logging.info(f"ربات @{me.username} اجرا شد.")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("ربات متوقف شد.")
