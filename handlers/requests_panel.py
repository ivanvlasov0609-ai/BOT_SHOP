import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db import Request, User, Lot, Product, AdminNotification
from handlers.lots import format_price_rub

router = Router()
log = logging.getLogger(__name__)

PAGE_SIZE = 10

def list_requests_kb(requests):
    rows = []
    for r in requests:
        title = f"#{r.id} • {r.target_type} {r.target_id} • {r.status}"
        rows.append([InlineKeyboardButton(text=title, callback_data=f"req_open:{r.id}")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def request_actions_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Вернуть уведомление", callback_data=f"req_resend:{req_id}")],
        [InlineKeyboardButton(text="⬅ К списку", callback_data="requests")]
    ])

@router.callback_query(F.data == "requests")
async def open_requests(call: CallbackQuery, session: AsyncSession):
    res = await session.execute(select(Request).order_by(Request.created_at.desc()).limit(PAGE_SIZE))
    reqs = res.scalars().all()
    if not reqs:
        await call.message.edit_caption(
            caption="📑 Заявок пока нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")]])
        )
        return
    await call.message.edit_caption(
        caption="📑 Последние заявки:",
        reply_markup=list_requests_kb(reqs)
    )

@router.callback_query(F.data.startswith("req_open:"))
async def req_open(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    # краткие детали
    target_info = ""
    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        target_info = f"Лот: <b>{lot.name if lot else '—'}</b>"
    else:
        product = await session.get(Product, req.target_id)
        target_info = f"Товар: <b>{product.name if product else '—'}</b>"

    text = (
        f"📄 <b>Заявка #{req.id}</b>\n"
        f"Тип: {req.target_type}\n"
        f"Сумма: {format_price_rub(req.total_amount)} (предоплата {format_price_rub(req.prepayment_amount)})\n"
        f"Статус: {req.status}\n"
        f"{target_info}\n"
        f"Создана: {req.created_at:%Y-%m-%d %H:%M}\n"
    )
    await call.message.edit_caption(caption=text, reply_markup=request_actions_kb(req.id))

@router.callback_query(F.data.startswith("req_resend:"))
async def req_resend(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    # текущий админ в нашей таблице пользователей
    res_admin = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin_user = res_admin.scalars().first()
    if not admin_user:
        await call.answer("Админ не найден", show_alert=True)
        return

    # соберём текст
    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        target_name = lot.name if lot else "Лот"
    else:
        product = await session.get(Product, req.target_id)
        target_name = product.name if product else "Товар"

    text = (
        f"📰 <b>Заявка (повторно)</b>\n\n"
        f"📝 ID: <code>{req.id}</code>\n"
        f"📦 {target_name}\n"
        f"💰 Сумма: {format_price_rub(req.total_amount)} | Предоплата: {format_price_rub(req.prepayment_amount)}\n"
        f"Статус: {req.status}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🙈 Скрыть это уведомление", callback_data=f"hide_req:{req.id}")]
    ])

    m = await call.bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=kb,
        disable_web_page_preview=True,
        disable_notification=False  # всегда со звуком
    )

    # сохраняем как новое уведомление
    session.add(AdminNotification(
        admin_user_id=admin_user.id,
        request_id=req.id,
        tg_message_id=m.message_id,
        is_hidden=False
    ))
    await session.commit()

    await call.answer("Отправлено ✅")
