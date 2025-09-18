from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from config import START_PHOTO
from db import Lot
from handlers.lots import format_price_rub
from config import GROUP_ID,ADMINS
from keyboards.inline import client_kb,admin_main_kb

router = Router()


@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery, session: AsyncSession):
    # Удаляем предыдущее сообщение (например, меню)
    try:
        await call.message.delete()
    except:
        pass

    result = await session.execute(select(Lot))
    lots = result.scalars().all()

    if not lots:
        await call.message.answer(
            "📦 Каталог пуст, пока нет доступных лотов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")]
            ])
        )
        return

    text_lines = ["📂 <b>Каталог лотов:</b>\n"]

    for lot in lots:
        status = "🟢 В наличии" if lot.is_active else "🔴 Продан"
        link = f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}" if lot.message_id else None

        line = (
            f"📦 <a href='{link}'>Лот ID: {lot.id}</a> | {lot.name}\n"
            f"💰 {format_price_rub(lot.price)}\n"
            f"{status}\n"
            f"──────────────────────"
        )
        text_lines.append(line)

    catalog_text = "\n".join(text_lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main_k")]
    ])

    await call.message.answer(catalog_text, disable_web_page_preview=True, reply_markup=kb)


# Возврат в главное меню клиента
@router.callback_query(F.data == "back_to_main_k")
async def back_to_main(call: CallbackQuery):
    # Удаляем текущее сообщение (любое, текст или фото)
    if call.from_user.id not in ADMINS:
        kb=admin_main_kb
    else:kb=client_kb
    # Отправляем стартовое фото и меню

    await call.message.answer_photo(
        photo=START_PHOTO,
        caption="👋 Добро пожаловать!\n\nВыберите действие ниже:",
        reply_markup=kb
    )
