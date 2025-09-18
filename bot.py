import asyncio
import logging
import platform
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram import __version__ as aiogram_version

from config import BOT_TOKEN
from handlers import start, raffle, lots, orders, catalog
from handlers import requests_panel  # <-- новый роутер
from db import init_db, get_session_middleware, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("app")

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.message.middleware(get_session_middleware())
    dp.callback_query.middleware(get_session_middleware())

    dp.include_router(start.router)
    dp.include_router(raffle.router)
    dp.include_router(lots.router)
    dp.include_router(orders.router)
    dp.include_router(catalog.router)
    dp.include_router(requests_panel.router)  # <-- подключили

    me = await bot.get_me()
    db_url = engine.url.render_as_string(hide_password=True)
    log.info("========== BOT START ==========")
    log.info("Bot: %s (@%s) | id=%s", me.first_name, me.username, me.id)
    log.info("Aiogram: %s | Python: %s | OS: %s", aiogram_version, sys.version.split()[0], platform.platform())
    log.info("Database: %s", db_url)
    log.info("Routers: %s", ", ".join(["start", "raffle", "lots", "orders", "catalog", "requests_panel"]))
    log.info("================================")

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Polling started. Listening for updates...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
