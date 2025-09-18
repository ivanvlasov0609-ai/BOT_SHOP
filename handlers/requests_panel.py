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
from config import GROUP_ID

router = Router()
log = logging.getLogger(__name__)

PAGE_SIZE = 10

RU_STATUS = {
    "pending":    ("🟢", "Новая"),
    "processing": ("🟠", "В работе"),
    "done":       ("🔴", "Закрыта"),
}
def s_badge(status: str) -> str:
    icon, name = RU_STATUS.get(status, ("⚪", status))
    return f"{icon} {name}"

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
        [InlineKeyboardButton(text=f"🟢 Новые ({counts['pending']})", callback_data="req_tab:pending")],
        [InlineKeyboardButton(text=f"🟠 В работе ({counts['processing']})", callback_data="req_tab:processing")],
        [InlineKeyboardButton(text=f"🔴 Закрытые ({counts['done']})", callback_data="req_tab:done")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")],
    ])

def _entry_title(r, name, price):
    return f"#{r.id} • {name} • {format_price_rub(price)} • {s_badge(r.status)}"

def list_requests_kb(entries):
    rows = []
    for r_id, title in entries:
        rows.append([InlineKeyboardButton(text=title, callback_data=f"req_open:{r_id}")])
    rows.append([InlineKeyboardButton(text="⬅ К разделам", callback_data="requests")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def combined_kb(req: Request, user_tg_id: int | None, lot_link: str | None):
    rows = []

    # действия
    if req.status == "pending":
        rows.append([InlineKeyboardButton(text="🛠 Взять в работу", callback_data=f"req_take:{req.id}")])
    elif req.status == "processing":
        rows.append([InlineKeyboardButton(text="✅ Закрыть заявку", callback_data=f"req_close:{req.id}")])
    # если закрыта — действий нет

    # ссылки (всегда)
    if user_tg_id:
        rows.append([InlineKeyboardButton(text="👤 Открыть клиента", url=f"tg://user?id={user_tg_id}")])
    if req.target_type == "lot" and lot_link:
        rows.append([InlineKeyboardButton(text="📦 Открыть лот", url=lot_link)])

    # «написать» только если не закрыта
    if req.status != "done":
        rows.append([InlineKeyboardButton(text="✉️ Написать клиенту", callback_data=f"req_msg:{req.id}")])

    rows.append([InlineKeyboardButton(text="⬅ К списку", callback_data=f"req_tab:{req.status}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def lot_link_or_none(lot) -> str | None:
    if not lot or not lot.message_id: return None
    return f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}"

# ---------- FSM messaging ----------
class RequestMessage(StatesGroup):
    wait_text = State()

# ---------- root ----------
@router.callback_query(F.data == "requests")
async def requests_root(call: CallbackQuery, session: AsyncSession):
    counts, total = await get_counts(session)
    await call.message.edit_caption(caption=f"📑 Заявки (всего: {total})", reply_markup=requests_root_kb(counts))

@router.callback_query(F.data.startswith("req_tab:"))
async def open_requests_tab(call: CallbackQuery, session: AsyncSession):
    status = call.data.split(":")[1]
    res = await session.execute(
        select(Request).where(Request.status == status).order_by(Request.created_at.desc()).limit(PAGE_SIZE)
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

    caption = f"📂 {s_badge(status)} заявки:"
    await call.message.edit_caption(caption=caption, reply_markup=list_requests_kb(entries))

# ---------- open card ----------
@router.callback_query(F.data.startswith("req_open:"))
async def req_open(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True); return

    photo = None
    lot_link = None
    title_line = ""
    price_val = req.total_amount

    if req.target_type == "lot":
        lot = await session.get(Lot, req.target_id)
        if lot:
            photo = lot.photo
            lot_link = lot_link_or_none(lot)
            title_line = f"📦 Лот: <b>{lot.name}</b>"
            price_val = lot.price
        else:
            title_line = "📦 Лот: —"
    else:
        product = await session.get(Product, req.target_id)
        title_line = f"🧾 Товар: <b>{product.name if product else '—'}</b>"
        price_val = product.price if product else price_val

    user = await session.get(User, req.user_id)
    client_line = f"Клиент: {user.full_name or ''} @{user.username}" if user else "Клиент: —"

    text = (
        f"📄 <b>Заявка #{req.id}</b>\n"
        f"Статус: {s_badge(req.status)}\n"
        f"{title_line}\n"
        f"{client_line}\n"
        f"Сумма: {format_price_rub(price_val)} (предоплата {format_price_rub(req.prepayment_amount)})\n"
        f"Создана: {req.created_at:%Y-%m-%d %H:%M}"
    )

    kb = combined_kb(req, user.tg_id if user else None, lot_link)

    if photo:
        try: await call.message.delete()
        except: pass
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
        if not admin_user: continue
        if current_admin_tg and admin_user.tg_id == current_admin_tg:
            continue
        if n.tg_message_id:
            try:
                await bot.delete_message(chat_id=admin_user.tg_id, message_id=n.tg_message_id)
            except Exception:
                pass
        n.is_hidden = True
    await session.commit()

# ---------- take / close ----------
@router.callback_query(F.data.startswith("req_take:"))
async def req_take(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True); return
    if req.status == "done":
        await call.answer("Заявка уже закрыта", show_alert=True); return
    if req.status == "processing":
        await call.answer("Заявка уже в работе", show_alert=True); return

    req.status = "processing"
    req.taken_at = datetime.utcnow()
    res_admin = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin = res_admin.scalars().first()
    if admin: req.taken_by_admin_id = admin.id
    await session.commit()

    # сообщим клиенту
    user = await session.get(User, req.user_id)
    if user:
        admin_name = call.from_user.full_name or (call.from_user.username and f"@{call.from_user.username}") or "администратор"
        await call.bot.send_message(
            chat_id=user.tg_id,
            text=(f"✅ Ваша заявка #{req.id} взята в работу.\n"
                  f"Ответственный: {admin_name}.")
        )

    await _delete_notifications_for_others(session, call.bot, req.id, call.from_user.id)
    await call.answer("Взято в работу ✅")
    await req_open(call, session)

@router.callback_query(F.data.startswith("req_close:"))
async def req_close(call: CallbackQuery, session: AsyncSession):
    req_id = int(call.data.split(":")[1])
    req = await session.get(Request, req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True); return
    if req.status == "done":
        await call.answer("Заявка уже закрыта", show_alert=True); return

    req.status = "done"
    req.closed_at = datetime.utcnow()
    await session.commit()

    # сообщим клиенту
    user = await session.get(User, req.user_id)
    if user:
        admin_name = call.from_user.full_name or (call.from_user.username and f"@{call.from_user.username}") or "администратор"
        await call.bot.send_message(
            chat_id=user.tg_id,
            text=(f"🧾 Ваша заявка #{req.id} закрыта.\n"
                  f"Закрыл: {admin_name}. Спасибо!")
        )

    await _delete_notifications_for_others(session, call.bot, req.id, None)
    await call.answer("Заявка закрыта ✅")
    await req_open(call, session)   # перерисуем карточку: действий больше нет

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
        await msg.answer("Клиент не найден."); await state.clear(); return
    await msg.bot.send_message(chat_id=user.tg_id, text=msg.text)
    await msg.answer("Отправлено ✅")
    await state.clear()
