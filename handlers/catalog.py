import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import START_PHOTO, GROUP_ID, ADMINS
from db import Lot
from handlers.lots import format_price_rub
from keyboards.inline import client_kb, build_admin_main_kb

router = Router()
log = logging.getLogger(__name__)

@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery, session: AsyncSession):
    try:
        await call.message.delete()
    except:
        pass

    res = await session.execute(select(Lot))
    lots = res.scalars().all()

    if not lots:
        await call.message.answer(
            "📦 Каталог пуст, пока нет доступных лотов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main_k")]
            ])
        )
        return

    lines = ["🗂 <b>Каталог лотов:</b>\n"]
    for lot in lots:
        status = "🟢 В наличии" if lot.is_active else "🔴 Нет в наличии"
        link = f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}" if lot.message_id else None
        lines.append(
            (f"📦 <a href='{link}'>Лот ID: {lot.id}</a> | {lot.name}\n" if link else
             f"📦 Лот ID: {lot.id} | {lot.name}\n")
            + f"💵 {format_price_rub(lot.price)}\n"
            + f"{status}\n"
            + "──────────────────────"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main_k")]
    ])
    await call.message.answer("\n".join(lines), disable_web_page_preview=True, reply_markup=kb)

@router.callback_query(F.data == "back_to_main_k")
async def back_to_main_k(call: CallbackQuery):
    try:
        await call.message.delete()
    except:
        pass

    kb = build_admin_main_kb() if call.from_user.id in ADMINS else client_kb
    await call.message.answer_photo(
        photo=START_PHOTO,
        caption="👋 Добро пожаловать!\n\nВыберите действие ниже:",
        reply_markup=kb
    )
