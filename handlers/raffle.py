from aiogram import Router, F
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

    await call.answer("🎉 Вы успешно присоединились к розыгрышу!", show_alert=True)
