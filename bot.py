import asyncio
import logging
import platform
import sys
import psutil  # <-- новая библиотека

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram import __version__ as aiogram_version

from config import BOT_TOKEN
from handlers import start, raffle, lots, orders, catalog,requests_cleanup
#from handlers import requests_panel  # <-- новый роутер
from handlers.requests_panel import routers as requests_routers
from db import init_db, get_session_middleware, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("app")


def log_system_stats():
    """Вывод статистики производительности ресурсов."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    log.info("=== SYSTEM STATS ===")
    log.info("CPU Load: %.1f%%", cpu_percent)
    log.info("Memory: %.1f%% used (%.2f / %.2f GB)",
             mem.percent, mem.used / 1e9, mem.total / 1e9)
    log.info("Disk: %.1f%% used (%.2f / %.2f GB)",
             disk.percent, disk.used / 1e9, disk.total / 1e9)
    net = psutil.net_io_counters()
    log.info("Network: Sent=%.2f MB | Received=%.2f MB",
             net.bytes_sent / 1e6, net.bytes_recv / 1e6)
    log.info("====================")


async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.message.middleware(get_session_middleware())
    dp.callback_query.middleware(get_session_middleware())

    dp.include_router(start.router)
    dp.include_router(raffle.router)
    for r in lots.routers:
        dp.include_router(r)
    for r in requests_routers:
        dp.include_router(r)
    dp.include_router(orders.router)
    dp.include_router(catalog.router)
    #dp.include_router(requests_panel.router)  # <-- подключили\
    dp.include_router(requests_cleanup.router)

    me = await bot.get_me()
    db_url = engine.url.render_as_string(hide_password=True)
    log.info("========== BOT START ==========")
    log.info("Bot: %s (@%s) | id=%s", me.first_name, me.username, me.id)
    log.info("Aiogram: %s | Python: %s | OS: %s",
             aiogram_version, sys.version.split()[0], platform.platform())
    log.info("Database: %s", db_url)
    log.info("Routers: %s", ", ".join(
        ["start", "raffle", "lots", "orders", "catalog", "requests_panel"]))
    log.info("================================")

    # Выводим статистику ресурсов при старте
    log_system_stats()

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Polling started. Listening for updates...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
