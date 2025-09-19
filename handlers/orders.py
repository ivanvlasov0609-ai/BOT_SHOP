import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import asyncio
from config import ADMINS, GROUP_ID
from db import Lot, User, Request, AdminNotification
from handlers.lots import format_price_rub  # из lots/__init__.py экспортируется
from config import PREPAY_PERCENT
router = Router()
log = logging.getLogger(__name__)

# ---------- утилиты вывода ----------
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
    # важна именно эта callback_data — как у тебя было
    rows.append([InlineKeyboardButton(text="🙈 Скрыть", callback_data=f"hide_req:{request_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- общие хелперы ----------
async def _ensure_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str | None) -> User:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    u = res.scalars().first()
    if not u:
        u = User(tg_id=tg_id, username=username, full_name=full_name)
        session.add(u)
        await session.commit()
        await session.refresh(u)
    return u

async def _send_admin_notification(bot: Bot, admin_id: int, text: str, kb: InlineKeyboardMarkup) -> int:
    m = await bot.send_message(
        chat_id=admin_id,
        text=text,
        reply_markup=kb,
        disable_web_page_preview=True,
        disable_notification=False
    )
    return m.message_id

# ----------- единый отправитель клиенту (тексты как у тебя) -----------
async def _send_client_created(bot: Bot, user_tg: int, req_id: int, lot_name: str, price: int, prepay: int, method: str):
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


# ----------- Купить (самовывоз) -----------
@router.callback_query(F.data.startswith("buy_lot:"))
async def client_buy_lot(call: CallbackQuery, session: AsyncSession):
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)
    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True)
        return

    user = await _ensure_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)

    prepay = lot.price * PREPAY_PERCENT // 100
    async with session.begin_nested():
        req = Request(
            user_id=user.id,
            target_type="lot",
            target_id=lot.id,
            prepayment_amount=prepay,
            total_amount=lot.price,
            status="pending",
            details="Самовывоз",
            created_at=datetime.utcnow(),
        )
        session.add(req)
        await session.flush()  # уже есть req.id внутри транзакции

    # тексты/клавиатура — как у тебя
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

    # ОТПРАВЛЯЕМ КЛИЕНТУ (как было)
    await _send_client_created(call.bot, user.tg_id, req.id, lot.name, lot.price, prepay, "pickup")

    # ПАРАЛЛЕЛЬНО РАССЫЛАЕМ АДМИНАМ
    send_tasks = []
    for admin_tg in ADMINS:
        send_tasks.append(_send_admin_notification(call.bot, admin_tg, text, kb))
    send_results = await asyncio.gather(*send_tasks, return_exceptions=True)

    # СОХРАНЯЕМ AdminNotification ТОЛЬКО ДЛЯ УСПЕШНЫХ ОТПРАВОК (АТОМАРНО)
    async with session.begin_nested():
        for admin_tg, res in zip(ADMINS, send_results):
            if isinstance(res, Exception):
                continue
            admin_user = await _ensure_user(session, admin_tg, None, None)
            session.add(AdminNotification(
                admin_user_id=admin_user.id,
                request_id=req.id,
                tg_message_id=res,
                is_hidden=False
            ))

    await call.answer("✅ Заявка создана. С вами скоро свяжутся!")


# ----------- Купить с доставкой -----------
@router.callback_query(F.data.startswith("buy_lot_delivery:"))
async def client_buy_lot_delivery(call: CallbackQuery, session: AsyncSession):
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)
    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True)
        return

    user = await _ensure_user(session, call.from_user.id, call.from_user.username, call.from_user.full_name)

    prepay = lot.price * PREPAY_PERCENT // 100
    async with session.begin():
        req = Request(
            user_id=user.id,
            target_type="lot",
            target_id=lot.id,
            prepayment_amount=prepay,
            total_amount=lot.price,
            status="pending",
            details="Доставка",
            created_at=datetime.utcnow(),
        )
        session.add(req)
        await session.flush()

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

    await _send_client_created(call.bot, user.tg_id, req.id, lot.name, lot.price, prepay, "delivery")

    send_tasks = []
    for admin_tg in ADMINS:
        send_tasks.append(_send_admin_notification(call.bot, admin_tg, text, kb))
    send_results = await asyncio.gather(*send_tasks, return_exceptions=True)

    async with session.begin():
        for admin_tg, res in zip(ADMINS, send_results):
            if isinstance(res, Exception):
                continue
            admin_user = await _ensure_user(session, admin_tg, None, None)
            session.add(AdminNotification(
                admin_user_id=admin_user.id,
                request_id=req.id,
                tg_message_id=res,
                is_hidden=False
            ))

    await call.answer("✅ Заявка с доставкой создана!")
