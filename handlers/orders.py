import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import ADMINS, GROUP_ID
from db import Lot, User, Request, AdminNotification
from handlers.lots import format_price_rub

router = Router()
log = logging.getLogger(__name__)

PREPAY_PERCENT = 20

def s_badge(status: str) -> str:
    return {"pending": "🟢 Новая", "processing": "🟠 В работе", "done": "🔴 Закрыта"}.get(status, status)

def fmt_dt_ru(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")

def admin_notify_kb(request_id: int, link: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🛠 Взять в работу", callback_data=f"req_take:{request_id}")]
    ]
    if link:
        rows.append([InlineKeyboardButton(text="🔗 К объявлению", url=link)])
    rows.append([InlineKeyboardButton(text="🙈 Скрыть", callback_data=f"hide_req:{request_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _ensure_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str | None) -> User:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    u = res.scalars().first()
    if not u:
        u = User(tg_id=tg_id, username=username, full_name=full_name)
        session.add(u); await session.commit(); await session.refresh(u)
    return u

async def _send_admin_notification(bot, admin_id: int, text: str, kb: InlineKeyboardMarkup) -> int:
    m = await bot.send_message(
        chat_id=admin_id, text=text, reply_markup=kb,
        disable_web_page_preview=True, disable_notification=False
    )
    return m.message_id

# ----------- общий отправитель клиенту -----------
async def _send_client_created(bot, user_tg: int, req_id: int, lot_name: str, price: int, prepay: int, method: str):
    await bot.send_message(
        chat_id=user_tg,
        text=(
            f"📢 <b>Ваша заявка #{req_id} принята</b>\n"
            f"🧾 Товар: {lot_name}\n"
            f"💰 Сумма: {format_price_rub(price)}\n"
            f"💳 Предоплата: {format_price_rub(prepay)}\n"
            f"{'🚚 Способ: Доставка' if method=='delivery' else '🚀 Способ: Самовывоз'}\n"
            f"🙏 Спасибо, что выбрали нас!"
        )
    )

# ----------- Купить без доставки -----------
@router.callback_query(F.data.startswith("buy_lot:"))
async def client_buy_lot(call: CallbackQuery, session: AsyncSession):
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)
    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True); return

    user = await _ensure_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)

    prepay = lot.price * PREPAY_PERCENT // 100
    req = Request(
        user_id=user.id, target_type="lot", target_id=lot.id,
        prepayment_amount=prepay, total_amount=lot.price,
        status="pending", details="Самовывоз",
        created_at=datetime.utcnow()
    )
    session.add(req); await session.commit()
    log.info("Request created: id=%s user_id=%s lot_id=%s", req.id, user.id, lot.id)

    # клиенту
    await _send_client_created(call.bot, user.tg_id, req.id, lot.name, lot.price, prepay, "pickup")

    # админам
    link = f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}" if lot.message_id else None
    kb = admin_notify_kb(req.id, link)
    text = (
        f"📢 <b>{s_badge('pending')}</b>\n\n"
        f"👤 Пользователь: {call.from_user.full_name} (@{call.from_user.username})\n"
        f"🆔 Telegram ID: <code>{call.from_user.id}</code>\n\n"
        f"📦 Лот: <b>{lot.name}</b>\n"
        f"💰 Цена: {format_price_rub(lot.price)}\n"
        f"💳 Предоплата: {format_price_rub(prepay)}\n"
        f"🗓 Создана: {fmt_dt_ru(req.created_at)}\n"
        f"🚀 Способ: Самовывоз\n"
        f"📝 Заявка ID: <code>{req.id}</code>"
    )

    for admin_tg in ADMINS:
        admin_user = await _ensure_user(session, admin_tg, None, None)
        msg_id = await _send_admin_notification(call.bot, admin_tg, text, kb)
        session.add(AdminNotification(
            admin_user_id=admin_user.id, request_id=req.id,
            tg_message_id=msg_id, is_hidden=False
        ))
    await session.commit()
    await call.answer("✅ Заявка создана. С вами скоро свяжутся!")

# ----------- Купить с доставкой -----------
@router.callback_query(F.data.startswith("buy_lot_delivery:"))
async def client_buy_lot_delivery(call: CallbackQuery, session: AsyncSession):
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)
    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True); return

    user = await _ensure_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)

    prepay = lot.price * PREPAY_PERCENT // 100
    req = Request(
        user_id=user.id, target_type="lot", target_id=lot.id,
        prepayment_amount=prepay, total_amount=lot.price,
        status="pending", details="Доставка",
        created_at=datetime.utcnow()
    )
    session.add(req); await session.commit()
    log.info("Request created (delivery): id=%s user_id=%s lot_id=%s", req.id, user.id, lot.id)

    # клиенту
    await _send_client_created(call.bot, user.tg_id, req.id, lot.name, lot.price, prepay, "delivery")

    link = f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}" if lot.message_id else None
    kb = admin_notify_kb(req.id, link)
    text = (
        f"📢 <b>{s_badge('pending')}</b>\n\n"
        f"👤 Пользователь: {call.from_user.full_name} (@{call.from_user.username})\n"
        f"🆔 Telegram ID: <code>{call.from_user.id}</code>\n\n"
        f"📦 Лот: <b>{lot.name}</b>\n"
        f"💰 Цена: {format_price_rub(lot.price)}\n"
        f"💳 Предоплата: {format_price_rub(prepay)}\n"
        f"🗓 Создана: {fmt_dt_ru(req.created_at)}\n"
        f"🚚 Способ: Доставка\n"
        f"📝 Заявка ID: <code>{req.id}</code>"
    )

    for admin_tg in ADMINS:
        admin_user = await _ensure_user(session, admin_tg, None, None)
        msg_id = await _send_admin_notification(call.bot, admin_tg, text, kb)
        session.add(AdminNotification(
            admin_user_id=admin_user.id, request_id=req.id,
            tg_message_id=msg_id, is_hidden=False
        ))
    await session.commit()
    await call.answer("✅ Заявка с доставкой создана!")

# ----------- «Скрыть уведомление» -----------
@router.callback_query(F.data.startswith("hide_req:"))
async def hide_admin_notification(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    res_admin = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin_user = res_admin.scalars().first()
    if admin_user:
        res_note = await session.execute(
            select(AdminNotification)
            .where(AdminNotification.admin_user_id == admin_user.id,
                   AdminNotification.request_id == req_id,
                   AdminNotification.is_hidden == False)
            .order_by(AdminNotification.created_at.desc())
        )
        note = res_note.scalars().first()
        if note:
            note.is_hidden = True
            await session.commit()
    try:
        await call.message.delete()
    except:
        pass
    await call.answer("Скрыто ✅")
