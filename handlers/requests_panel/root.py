import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from keyboards.inline import requests_root_kb
from db import Request, User, AdminUIState
from config import PHOTOS
from utils.ui import update_panel
from keyboards.inline import requests_root_kb

router = Router()
log = logging.getLogger(__name__)

async def get_counts(session: AsyncSession):
    counts = {}
    total = 0
    for st in ("pending", "processing", "done"):
        res = await session.execute(select(func.count(Request.id)).where(Request.status == st))
        counts[st] = int(res.scalar() or 0)
        total += counts[st]
    return counts, total

@router.callback_query(F.data == "requests")
async def requests_root(call: CallbackQuery, session: AsyncSession):
    """Вход в раздел заявок из админ-панели"""
    await call.answer()
    counts, total = await get_counts(session)

    await update_panel(
        call.message,
        PHOTOS["requests_panel"],
        f"📑 Заявки (всего: {total})",
        requests_root_kb(counts)
    )
    m = call.message

    # сохраняем id сообщения панели заявок для автообновления
    res = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin = res.scalars().first()
    if admin:
        q2 = await session.execute(select(AdminUIState).where(AdminUIState.admin_user_id == admin.id))
        row = q2.scalars().first()
        if not row:
            row = AdminUIState(admin_user_id=admin.id, last_requests_message_id=m.message_id)
            session.add(row)
        else:
            row.last_requests_message_id = m.message_id
        await session.commit()