import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db import Request, Lot, Product, User
from config import GROUP_ID
from handlers.lots.utils import format_price_rub
from keyboards.inline import combined_kb
from handlers.requests_panel.utils import fmt_dt_ru, s_badge, lot_status_dot

router = Router()
log = logging.getLogger(__name__)

def lot_link_or_none(lot: Lot | None) -> str | None:
    if not lot or not lot.message_id:
        return None
    return f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}"

@router.callback_query(F.data.startswith("req_open:"))
async def req_open(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    photo = None
    lot_link = None
    title_line = ""
    price_val = req.total_amount

    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        if lot:
            photo = lot.photo
            lot_link = lot_link_or_none(lot)
            title_line = f"📦 Лот({lot.id}){lot_status_dot(lot)}: {lot.name}"
            price_val = lot.price
        else:
            title_line = f"📦 Лот({req.target_id})🔴: —"
    else:
        product = await session.get(Product, req.target_id)
        title_line = f"🧾 Товар({req.target_id}): {product.name if product else '—'}"
        price_val = product.price if product else price_val

    user = await session.get(User, req.user_id)
    client_line = f"Клиент: {user.full_name or ''} @{user.username}" if user else "Клиент: —"

    exec_line = "Исполнитель: —"
    if req.taken_by_admin_id:
        executor = await session.get(User, req.taken_by_admin_id)
        if executor:
            at = f"@{executor.username}" if executor.username else ""
            exec_line = f"Исполнитель: {executor.full_name or ''} {at}".strip()

    text = (
        f"📄 Заявка #{req.id} | Статус: {s_badge(req.status)}\n\n"
        f"{title_line}\n"
        f"{client_line}\n"
        f"{exec_line}\n\n"
        f"Сумма: {format_price_rub(price_val)} (предоплата {format_price_rub(req.prepayment_amount)})\n"
        f"🗓 Создана: {fmt_dt_ru(req.created_at)}\n"
        f"🟠 Начата: {fmt_dt_ru(req.taken_at)}\n"
        f"🔴 Завершена: {fmt_dt_ru(req.closed_at)}"
    )

    kb = combined_kb(req, user.tg_id if user else None, lot_link)

    if photo:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer_photo(photo=photo, caption=text, reply_markup=kb)
    else:
        await call.message.edit_caption(caption=text, reply_markup=kb)
