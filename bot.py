import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from handlers import start, raffle, lots,orders, catalog
from db import init_db, get_session_middleware
from aiogram.fsm.storage.memory import MemoryStorage
import logging


async def main():

    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем middleware для сессии БД
    dp.message.middleware(get_session_middleware())
    dp.callback_query.middleware(get_session_middleware())
    dp.include_router(start.router)
    dp.include_router(raffle.router)
    dp.include_router(lots.router)
    dp.include_router(orders.router)
    dp.include_router(catalog.router)

    logging.info("Запуск бота")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
