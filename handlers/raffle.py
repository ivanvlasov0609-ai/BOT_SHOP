"""from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

from db import Raffle, RaffleParticipant

router = Router()

@router.callback_query(F.data == "raffle")
async def participate_in_raffle(call: CallbackQuery, session: AsyncSession):
    user_id = call.from_user.id

    # Проверяем активный розыгрыш
    result = await session.execute(
        select(Raffle).where(
            Raffle.is_active == True,
            Raffle.start_at <= datetime.utcnow(),
            Raffle.end_at >= datetime.utcnow()
        )
    )
    raffle = result.scalars().first()

    if not raffle:
        await call.answer("❌ Активных розыгрышей сейчас нет", show_alert=True)
        return

    # Проверяем, участвует ли пользователь
    result = await session.execute(
        select(RaffleParticipant).where(
            RaffleParticipant.raffle_id == raffle.id,
            RaffleParticipant.user_id == user_id
        )
    )
    participant = result.scalars().first()

    if participant:
        await call.answer("⚠️ Вы уже участвуете в этом розыгрыше!", show_alert=True)
        return

    # Добавляем нового участника
    new_participant = RaffleParticipant(raffle_id=raffle.id, user_id=user_id)
    session.add(new_participant)
    await session.commit()

    await call.answer("🎉 Вы успешно присоединились к розыгрышу!", show_alert=True)"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

from db import Raffle, RaffleParticipant

router = Router()


@router.callback_query(F.data == "raffle")
async def raffle_handler(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Обработка участия в розыгрыше"""
    raffle = (await session.execute(select(Raffle).where(Raffle.is_active == True))).scalar_one_or_none()
    if not raffle:
        await callback.answer("Нет активных розыгрышей ❌", show_alert=True)
        return

    now = datetime.utcnow()
    if raffle.start_at and now < raffle.start_at:
        await callback.answer("Розыгрыш ещё не начался ⏳", show_alert=True)
        return

    if raffle.end_at and now > raffle.end_at:
        await callback.answer("Розыгрыш уже завершён 🏁", show_alert=True)
        return

    # Проверяем участие
    participant_exists = (
        await session.execute(
            select(RaffleParticipant).where(
                RaffleParticipant.raffle_id == raffle.id,
                RaffleParticipant.user_id == callback.from_user.id
            )
        )
    ).scalar_one_or_none()

    if participant_exists:
        await callback.answer("️️⚠️ ️ Вы уже участвуете в этом розыгрыше!", show_alert=True)
        return

    # Добавляем участника
    participant = RaffleParticipant(raffle_id=raffle.id, user_id=callback.from_user.id)
    session.add(participant)
    await session.commit()

    await callback.answer("Вы успешно участвуете в розыгрыше 🎉", show_alert=True)


async def finish_raffle(bot: Bot, session: AsyncSession, raffle_id: int):
    """Завершение розыгрыша и уведомление участников"""
    raffle = await session.get(Raffle, raffle_id)
    if not raffle:
        return

    participants = (
        await session.execute(
            select(RaffleParticipant).where(RaffleParticipant.raffle_id == raffle.id)
        )
    ).scalars().all()

    raffle.is_active = False
    raffle.updated_at = datetime.utcnow()
    await session.commit()

    for p in participants:
        try:
            await bot.send_message(p.user_id, f"🏁 Розыгрыш '{raffle.title}' завершён!")
        except Exception:
            pass
