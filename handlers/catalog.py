import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import START_PHOTO, ADMINS
from db import Lot
from handlers.lots import format_price_rub
from keyboards.inline import client_kb, build_admin_main_kb

router = Router()
log = logging.getLogger(__name__)


def _availability(is_active: bool) -> str:
    return "🟢 В наличии" if is_active else "🔴 Продан"


@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery, session: AsyncSession):
    """Вывод каталога лотов ОДНИМ сообщением, как у тебя было раньше."""
    result = await session.execute(select(Lot))
    lots = result.scalars().all()

    if not lots:
        # если пусто — просто вернёмся на старт с меню
        try:
            await call.answer("📦 Каталог пуст.",show_alert=True)
        except Exception:
            await call.answer("📦 Каталог пуст.",show_alert=True)
        return
    else:
        try:
            await call.message.delete()
        except Exception:
            pass

    # формируем текст каталога
    lines = ["📂 <b>Каталог лотов:</b>", ""]
    for lot in lots:
        lines.append(f"📦 <b>Лот ID: {lot.id}</b> | {lot.name}")
        lines.append(f"💰 {format_price_rub(lot.price)}")
        lines.append(_availability(lot.is_active))
        lines.append("──────────────────────")
    text = "\n".join(lines).rstrip("─\n")

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main_k")]]
    )

    await call.message.answer(text, reply_markup=back_kb)


@router.callback_query(F.data == "back_to_main_k")
async def back_to_main(call: CallbackQuery):
    """Возврат в главное меню (как было)."""
    try:
        await call.message.delete()
    except Exception:
        pass

    try:
        await call.message.answer_photo(
            FSInputFile(START_PHOTO),
            caption="🏠 Главное меню",
            reply_markup=client_kb if call.from_user.id not in ADMINS else build_admin_main_kb()
        )
    except Exception:
        await call.message.answer(
            "🏠 Главное меню",
            reply_markup=client_kb if call.from_user.id not in ADMINS else build_admin_main_kb()
        )
