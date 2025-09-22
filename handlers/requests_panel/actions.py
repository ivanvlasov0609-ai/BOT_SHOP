import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db import Request, User, Lot, AdminNotification
from handlers.lots.utils import format_price_rub
from handlers.requests_panel.utils import fmt_dt_ru, s_badge
from handlers.requests_panel.view import req_open
from sqlalchemy import func
from db import User, Request, AdminUIState
from aiogram.types import FSInputFile
from config import PHOTOS
from keyboards.inline import build_admin_panel_kb,requests_root_kb
from utils.ui import update_panel
router = Router()
log = logging.getLogger(__name__)

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ НОТИФИКАЦИЙ
# ============================================================
async def _delete_notifications_for_others(session: AsyncSession, bot, req_id: int, current_admin_tg: int | None):
    """Скрываем уведомления о заявке у других админов"""
    res_notes = await session.execute(
        select(AdminNotification).where(AdminNotification.request_id == req_id, AdminNotification.is_hidden == False)
    )
    notes = res_notes.scalars().all()
    for n in notes:
        admin_user = await session.get(User, n.admin_user_id)
        if not admin_user:
            continue
        if current_admin_tg and admin_user.tg_id == current_admin_tg:
            continue
        if n.tg_message_id:
            try:
                await bot.delete_message(chat_id=admin_user.tg_id, message_id=n.tg_message_id)
            except Exception:
                pass
        n.is_hidden = True
    await session.commit()


async def _edit_my_notification(session: AsyncSession, bot, req: Request, admin_tg_id: int, link: str | None):
    """Обновляем уведомление у текущего админа"""
    res_admin = await session.execute(select(User).where(User.tg_id == admin_tg_id))
    me = res_admin.scalars().first()
    if not me:
        return
    res_note = await session.execute(
        select(AdminNotification)
        .where(AdminNotification.admin_user_id == me.id, AdminNotification.request_id == req.id, AdminNotification.is_hidden == False)
        .order_by(AdminNotification.created_at.desc())
    )
    note = res_note.scalars().first()
    if not note or not note.tg_message_id:
        return

    buyer = await session.get(User, req.user_id)
    buyer_line = f"{buyer.full_name or ''} (@{buyer.username})" if buyer else "—"

    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        name = lot.name if lot else "Лот"
        price = lot.price if lot else req.total_amount
        text = (
            f"{'📢' if req.status=='pending' else '🛎'} <b>{s_badge(req.status)}</b>\n\n"
            f"👤 Пользователь: {buyer_line}\n"
            f"🆔 Telegram ID: <code>{buyer.tg_id if buyer else ''}</code>\n\n"
            f"📦 Лот: <b>{name}</b>\n"
            f"💰 Цена: {format_price_rub(price)}\n"
            f"💳 Предоплата: {format_price_rub(req.prepayment_amount)}\n"
            f"🗓 Создана: {fmt_dt_ru(req.created_at)}\n"
            f"📝 Заявка ID: <code>{req.id}</code>"
        )
    else:
        text = f"🛎 <b>{s_badge(req.status)}</b>\n\n📝 Заявка ID: <code>{req.id}</code>"

    rows = []
    if link:
        rows.append([InlineKeyboardButton(text="🔗 К объявлению", url=link)])
    rows.append([InlineKeyboardButton(text="🙈 Скрыть", callback_data=f"hide_req:{req.id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    try:
        await bot.edit_message_text(
            chat_id=admin_tg_id,
            message_id=note.tg_message_id,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True
        )
    except Exception:
        pass

# ============================================================
# FSM для отправки сообщения клиенту
# ============================================================
class RequestMessage(StatesGroup):
    wait_text = State()

# ============================================================
# ОБРАБОТЧИКИ ДЕЙСТВИЙ
# ============================================================
@router.callback_query(F.data.startswith("req_take:"))
async def req_take(call: CallbackQuery, session: AsyncSession):
    """Взять заявку в работу"""
    await call.answer()
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        return await call.answer("Заявка не найдена", show_alert=True)
    if req.status == "processing":
        return await call.answer("Заявка уже в работе", show_alert=True)

    req.status = "processing"
    req.taken_at = datetime.utcnow()
    res_admin = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin = res_admin.scalars().first()
    if admin:
        req.taken_by_admin_id = admin.id
    await session.commit()

    # уведомляем клиента
    user = await session.get(User, req.user_id)
    if user:
        admin_name = call.from_user.full_name or (call.from_user.username and f"@{call.from_user.username}") or "администратор"
        await call.bot.send_message(
            chat_id=user.tg_id,
            text=(f"✅ Ваша заявка №{req.id} взята в работу\n"
                  f"👨‍💼 Менеджер: {admin_name}\n"
                  f"🗓 {fmt_dt_ru(datetime.utcnow())}")
        )

    await _delete_notifications_for_others(session, call.bot, req.id, call.from_user.id)
    await _edit_my_notification(session, call.bot, req, call.from_user.id, None)

    await req_open(call, session)


@router.callback_query(F.data.startswith("req_close:"))
async def req_close(call: CallbackQuery, session: AsyncSession):
    """Закрыть заявку"""
    await call.answer()
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        return await call.answer("Заявка не найдена", show_alert=True)
    if req.status == "done":
        return await call.answer("Заявка уже закрыта", show_alert=True)

    req.status = "done"
    req.closed_at = datetime.utcnow()
    await session.commit()

    user = await session.get(User, req.user_id)
    if user:
        admin_name = call.from_user.full_name or (call.from_user.username and f"@{call.from_user.username}") or "администратор"
        await call.bot.send_message(
            chat_id=user.tg_id,
            text=(f"🧾 Заявка №{req.id} закрыта\n"
                  f"👨‍💼 Закрыл: {admin_name}\n"
                  f"🗓 Период: {fmt_dt_ru(req.taken_at)} — {fmt_dt_ru(req.closed_at)}\n"
                  f"🙏 Спасибо, что выбрали нас!")
        )

    await _delete_notifications_for_others(session, call.bot, req.id, None)
    await _edit_my_notification(session, call.bot, req, call.from_user.id, None)

    await req_open(call, session)


@router.callback_query(F.data.startswith("req_toggle_lot:"))
async def req_toggle_lot(call: CallbackQuery, session: AsyncSession):
    """Переключить статус лота"""
    await call.answer()
    from handlers.lots.utils import refresh_lot_keyboard  # локальный импорт чтобы избежать циклов

    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req or req.target_type != "lot":
        return await call.answer("Лот не найден для этой заявки", show_alert=True)

    lot = await session.get(Lot, req.target_id)
    if not lot:
        return await call.answer("Лот не найден", show_alert=True)

    lot.is_active = not bool(lot.is_active)
    await session.commit()

    # обновляем клавиатуру под постом лота
    await refresh_lot_keyboard(call.bot, lot)

    await call.answer("Статус лота обновлён ✅")
    await req_open(call, session)


@router.callback_query(F.data.startswith("req_msg:"))
async def req_msg_begin(call: CallbackQuery, state: FSMContext):
    """Начало диалога с клиентом"""
    await call.answer()
    await state.update_data(req_id=int(call.data.split(":")[1]))
    await state.set_state(RequestMessage.wait_text)
    await call.message.answer("Напишите текст для клиента (или /cancel):")


@router.message(RequestMessage.wait_text)
async def req_msg_send(msg: Message, state: FSMContext, session: AsyncSession):
    """Отправка сообщения клиенту"""
    data = await state.get_data()
    req = await session.get(Request, int(data["req_id"])) if data else None
    user = await session.get(User, req.user_id) if req else None
    if not user:
        await msg.answer("Клиент не найден.")
        await state.clear()
        return

    await msg.bot.send_message(chat_id=user.tg_id, text=msg.text)
    await msg.answer("Отправлено ✅")
    await state.clear()
async def refresh_admin_panel(bot, session: AsyncSession, admin: User):
    """Обновить сообщение админ-панели для конкретного админа"""
    # считаем заявки в статусе pending
    q = await session.execute(
        select(func.count(Request.id)).where(Request.status == "pending")
    )
    pending_count = int(q.scalar() or 0)

    # ищем id последнего сообщения панели у этого админа
    q2 = await session.execute(
        select(AdminUIState).where(AdminUIState.admin_user_id == admin.id)
    )
    ui_state = q2.scalars().first()
    if not ui_state or not ui_state.last_menu_message_id:
        return

    try:
        await bot.edit_message_media(
            chat_id=admin.tg_id,
            message_id=ui_state.last_menu_message_id,
            media={
                "type": "photo",
                "media": FSInputFile(PHOTOS["admin_panel"]),
                "caption": "⚙ Панель администратора:\nВыберите раздел:",
            },
            reply_markup=build_admin_panel_kb(pending_count)
        )
    except Exception as e:
        print(f"[refresh_admin_panel] Ошибка обновления панели {admin.tg_id}: {e}")
@router.callback_query(F.data.startswith("hide_req:"))
async def hide_request_notification(call: CallbackQuery, session: AsyncSession):
    """Админ скрывает уведомление о заявке у себя"""
    await call.answer("Уведомление скрыто ✅", show_alert=False)

    req_id = int(call.data.split(":")[1])

    # находим запись уведомления
    res_note = await session.execute(
        select(AdminNotification).where(
            AdminNotification.request_id == req_id,
            AdminNotification.is_hidden == False
        )
    )
    note = res_note.scalars().first()
    if not note:
        try:
            await call.message.delete()
        except Exception:
            pass
        return

    # помечаем как скрытое
    note.is_hidden = True
    await session.commit()

    # удаляем сообщение у админа
    try:
        await call.message.delete()
    except Exception:
        pass
async def refresh_requests_panel(bot, session: AsyncSession, admin: User):
    """Обновить панель заявок у конкретного админа"""
    counts = {}
    total = 0
    for st in ("pending", "processing", "done"):
        q = await session.execute(select(func.count(Request.id)).where(Request.status == st))
        counts[st] = int(q.scalar() or 0)
        total += counts[st]

    q2 = await session.execute(select(AdminUIState).where(AdminUIState.admin_user_id == admin.id))
    ui_state = q2.scalars().first()
    if not ui_state or not ui_state.last_requests_message_id:
        return

    try:
        await bot.edit_message_media(
            chat_id=admin.tg_id,
            message_id=ui_state.last_requests_message_id,
            media={
                "type": "photo",
                "media": FSInputFile(PHOTOS["requests_panel"]),
                "caption": f"📑 Заявки (всего: {total})",
            },
            reply_markup=requests_root_kb(counts)
        )
    except Exception as e:
        print(f"[refresh_requests_panel] Ошибка обновления панели заявок {admin.tg_id}: {e}")