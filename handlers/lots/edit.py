import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from db import Lot
from .keyboards import get_lots_keyboard

router = Router()


class LotEditState(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_price = State()


@router.callback_query(F.data.startswith("lot_edit_"))
async def start_edit(callback: CallbackQuery, state: FSMContext):
    lot_id = int(callback.data.split("_")[-1])
    await state.set_state(LotEditState.waiting_for_new_name)
    await state.update_data(lot_id=lot_id)
    await callback.message.answer("✍ Введите новое название для лота")


@router.message(LotEditState.waiting_for_new_name)
async def edit_name(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    lot = await session.get(Lot, data["lot_id"])
    if not lot:
        await message.answer("❌ Лот не найден")
        await state.clear()
        return

    lot.name = message.text
    await session.commit()

    await state.set_state(LotEditState.waiting_for_new_price)
    await message.answer("💰 Введите новую цену")


@router.message(LotEditState.waiting_for_new_price)
async def edit_price(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    lot = await session.get(Lot, data["lot_id"])
    if not lot:
        await message.answer("❌ Лот не найден")
        await state.clear()
        return

    try:
        lot.price = int(message.text)
    except ValueError:
        await message.answer("❌ Цена должна быть числом")
        return

    await session.commit()
    await message.answer("✅ Лот успешно обновлён", reply_markup=get_lots_keyboard())
    await state.clear()
