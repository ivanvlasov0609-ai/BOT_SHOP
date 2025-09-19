import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from db import Request, User, Lot, Product, AdminNotification
from handlers.lots import format_price_rub
from config import GROUP_ID,START_PHOTO

router = Router()
log = logging.getLogger(__name__)

PAGE_SIZE = 10
TRIM_LEN = 48
RU_STATUS = {
    "pending":    ("🟢", "Новая"),
    "processing": ("🟠", "В работе"),
    "done":       ("🔴", "Закрыта"),
}
def s_icon(status: str) -> str:
    return RU_STATUS.get(status, ("⚪", ""))[0]
def s_badge(status: str) -> str:
    icon, name = RU_STATUS.get(status, ("⚪", status))
    return f"{icon} {name}"

def lot_status_dot(lot) -> str:
    return "🟢" if (lot and getattr(lot, "is_active", False)) else "🔴"

def fmt_dt_ru(dt: datetime | None) -> str:
    return dt.strftime("%d.%m.%Y %H:%M") if dt else "—"

# ---------- counters ----------
async def get_counts(session: AsyncSession):
    counts = {}
    total = 0
    for st in ("pending", "processing", "done"):
        res = await session.execute(select(func.count(Request.id)).where(Request.status == st))
        counts[st] = int(res.scalar() or 0)
        total += counts[st]
    return counts, total

# ---------- keyboards ----------
def requests_root_kb(counts):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🟢 Новые ({counts['pending']})", callback_data="req_tab:pending:0")],
        [InlineKeyboardButton(text=f"🟠 В работе ({counts['processing']})", callback_data="req_tab:processing:0")],
        [InlineKeyboardButton(text=f"🔴 Закрытые ({counts['done']})", callback_data="req_tab:done:0")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")],
    ])

def _entry_title(r: Request, name: str, price: int):
    # подрежем слишком длинные названия
    if name and len(name) > TRIM_LEN:
        name = name[:TRIM_LEN - 1] + "…"
    # формат: 🔴 #12 • Название • 62.800 руб.
    return f"{s_icon(r.status)} #{r.id} • {name} • {format_price_rub(price)}"

def list_requests_kb(entries, status: str, page: int, total_pages: int):
    rows = []
    for r_id, title in entries:
        rows.append([InlineKeyboardButton(text=title, callback_data=f"req_open:{r_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⟨ Назад", callback_data=f"req_tab:{status}:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд ⟩", callback_data=f"req_tab:{status}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅ К разделам", callback_data="requests")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def combined_kb(req: Request, user_tg_id: int | None, lot_link: str | None):
    rows = []

    # действия по заявке
    if req.status == "pending":
        rows.append([InlineKeyboardButton(text="🛠 Взять в работу", callback_data=f"req_take:{req.id}")])
    elif req.status == "processing":
        rows.append([InlineKeyboardButton(text="✅ Закрыть заявку", callback_data=f"req_close:{req.id}")])
    elif req.status == "done":
        rows.append([InlineKeyboardButton(text="🔄 Взять в работу снова", callback_data=f"req_take:{req.id}")])

    # блок по лоту
    if req.target_type == "lot":
        rows.append([InlineKeyboardButton(text="🔁 Сменить статус лота", callback_data=f"req_toggle_lot:{req.id}")])
        if lot_link:
            rows.append([InlineKeyboardButton(text="📦 Открыть лот", url=lot_link)])

    # ссылки/связь с клиентом
    if user_tg_id:
        rows.append([InlineKeyboardButton(text="👤 Открыть клиента", url=f"tg://user?id={user_tg_id}")])

    if req.status != "done":
        rows.append([InlineKeyboardButton(text="✉️ Написать клиенту", callback_data=f"req_msg:{req.id}")])

    rows.append([InlineKeyboardButton(text="⬅ К списку", callback_data=f"req_tab:{req.status}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def lot_link_or_none(lot: Lot | None) -> str | None:
    if not lot or not lot.message_id:
        return None
    return f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}"

# ---------- FSM messaging ----------
class RequestMessage(StatesGroup):
    wait_text = State()

# ---------- root ----------
@router.callback_query(F.data == "requests")
async def requests_root(call: CallbackQuery, session: AsyncSession):
    counts, total = await get_counts(session)

    # вместо edit_caption — удаляем и отправляем новое с нужной фоткой
    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_photo(
        photo=START_PHOTO,
        caption=f"📑 Заявки (всего: {total})",
        reply_markup=requests_root_kb(counts)
    )


@router.callback_query(F.data.startswith("req_tab:"))
async def open_requests_tab(call: CallbackQuery, session: AsyncSession):
    # формат: req_tab:{status}:{page}
    parts = call.data.split(":")
    status = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    # всего заявок с этим статусом
    qcnt = await session.execute(select(func.count(Request.id)).where(Request.status == status))
    total = int(qcnt.scalar() or 0)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    # последние сначала (с пагинацией)
    offset = page * PAGE_SIZE
    res = await session.execute(
        select(Request)
        .where(Request.status == status)
        .order_by(Request.created_at.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    reqs = res.scalars().all()

    entries = []
    for r in reqs:
        name, price = "—", r.total_amount
        if r.target_type == "lot":
            lot = await session.get(Lot, r.target_id)
            if lot:
                name, price = lot.name, lot.price
        else:
            product = await session.get(Product, r.target_id)
            if product:
                name, price = product.name, product.price
        entries.append((r.id, _entry_title(r, name, price)))

    caption = f"📂 {s_badge(status)} заявки (стр. {page+1}/{total_pages}):"
    await call.message.edit_caption(caption=caption, reply_markup=list_requests_kb(entries, status, page, total_pages))

# ---------- open card ----------
@router.callback_query(F.data.startswith("req_open:"))
async def req_open(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    photo = None
    lot_link = None
    title_line = ""
    price_val = req.total_amount
    lot = None
    product = None

    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        if lot:
            photo = lot.photo
            lot_link = lot_link_or_none(lot)
            # 📦 Лот(4432)🔴: Смартфон ...
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

    # исполнитель
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

# ---------- sync notifications ----------
async def _delete_notifications_for_others(session: AsyncSession, bot, req_id: int, current_admin_tg: int | None):
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

# ---------- take / close ----------
@router.callback_query(F.data.startswith("req_take:"))
async def req_take(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return
    if req.status == "processing":
        await call.answer("Заявка уже в работе", show_alert=True)
        return

    req.status = "processing"
    req.taken_at = datetime.utcnow()
    res_admin = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin = res_admin.scalars().first()
    if admin:
        req.taken_by_admin_id = admin.id
    await session.commit()

    # клиенту
    user = await session.get(User, req.user_id)
    if user:
        admin_name = call.from_user.full_name or (call.from_user.username and f"@{call.from_user.username}") or "администратор"
        await call.bot.send_message(
            chat_id=user.tg_id,
            text=(
                f"✅ Ваша заявка №{req.id} взята в работу\n"
                f"👨‍💼 Менеджер: {admin_name}\n"
                f"🗓 {fmt_dt_ru(datetime.utcnow())}"
            )
        )

    await _delete_notifications_for_others(session, call.bot, req.id, call.from_user.id)

    link = None
    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        link = lot_link_or_none(lot)
    await _edit_my_notification(session, call.bot, req, call.from_user.id, link)

    await call.answer("Взято в работу ✅")
    await req_open(call, session)

@router.callback_query(F.data.startswith("req_close:"))
async def req_close(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return
    if req.status == "done":
        await call.answer("Заявка уже закрыта", show_alert=True)
        return

    req.status = "done"
    req.closed_at = datetime.utcnow()
    await session.commit()

    # клиенту
    user = await session.get(User, req.user_id)
    if user:
        admin_name = call.from_user.full_name or (call.from_user.username and f"@{call.from_user.username}") or "администратор"
        await call.bot.send_message(
            chat_id=user.tg_id,
            text=(
                f"🧾 Заявка №{req.id} закрыта\n"
                f"👨‍💼 Закрыл: {admin_name}\n"
                f"🗓 Период: {fmt_dt_ru(req.taken_at)} — {fmt_dt_ru(req.closed_at)}\n"
                f"🙏 Спасибо, что выбрали нас!"
            )
        )

    await _delete_notifications_for_others(session, call.bot, req.id, None)

    link = None
    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        link = lot_link_or_none(lot)
    await _edit_my_notification(session, call.bot, req, call.from_user.id, link)

    await call.answer("Заявка закрыта ✅")
    await req_open(call, session)

# ---------- toggle lot status ----------
@router.callback_query(F.data.startswith("req_toggle_lot:"))
async def req_toggle_lot(call: CallbackQuery, session: AsyncSession):
    from handlers.lots import refresh_lot_keyboard  # <-- импорт тут, чтобы не было циклов на уровне модуля

    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req or req.target_type != "lot":
        await call.answer("Лот не найден для этой заявки", show_alert=True)
        return

    lot = await session.get(Lot, req.target_id)
    if not lot:
        await call.answer("Лот не найден", show_alert=True)
        return

    # Тогглим статус
    lot.is_active = not bool(lot.is_active)
    await session.commit()

    # ⚠️ Сразу обновляем клавиатуру под постом лота в группе
    await refresh_lot_keyboard(call.bot, lot)

    await call.answer("Статус лота обновлён ✅")
    # Перерисовываем карточку заявки (чтобы точка 🔴/🟢 обновилась)
    await req_open(call, session)


# ---------- messaging client ----------
class RequestMessage(StatesGroup):
    wait_text = State()

@router.callback_query(F.data.startswith("req_msg:"))
async def req_msg_begin(call: CallbackQuery, state: FSMContext):
    await state.update_data(req_id=int(call.data.split(":")[1]))
    await state.set_state(RequestMessage.wait_text)
    await call.message.answer("Напишите текст для клиента (или /cancel):")

@router.message(RequestMessage.wait_text)
async def req_msg_send(msg: Message, state: FSMContext, session: AsyncSession):
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
