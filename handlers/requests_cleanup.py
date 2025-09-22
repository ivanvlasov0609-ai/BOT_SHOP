# handlers/requests_cleanup.py
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from db import Request, AdminNotification
from keyboards.inline import back_kb  # если нужно, либо соберём локально

router = Router()
log = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("requests_cleanup_do:"))
async def requests_cleanup_do(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    days = int(call.data.split(":")[1])
    threshold = datetime.utcnow() - timedelta(days=days)

    # найдём id заявок, которые удаляем
    res = await session.execute(
        select(Request.id).where(Request.status == "done").where(Request.created_at < threshold)
    )
    req_ids = res.scalars().all()

    if not req_ids:
        await call.answer("Нет заявок для удаления.", show_alert=True)
        return

    # удаляем связанные уведомления
    del_notes = await session.execute(
        delete(AdminNotification).where(AdminNotification.request_id.in_(req_ids))
    )
    # удаляем сами заявки
    del_reqs = await session.execute(
        delete(Request).where(Request.id.in_(req_ids))
    )
    await session.commit()

    deleted_notes = del_notes.rowcount or 0
    deleted_reqs = del_reqs.rowcount or len(req_ids)

    await call.message.edit_text(
        f"✅ Удалено заявок: <b>{deleted_reqs}</b>\n"
        f"🗒 Удалено уведомлений: <b>{deleted_notes}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Назад к заявкам", callback_data="requests")],
            [InlineKeyboardButton(text="🏠 В панель", callback_data="open_admin_panel")],
        ])
    )
