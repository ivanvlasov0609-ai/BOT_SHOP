import logging
import re
import html
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from config import ADMINS, GROUP_ID
from db import Lot, User
from keyboards.inline import lots_menu_kb, back_kb
from config import START_PHOTO

router = Router()
log = logging.getLogger(__name__)

# ---------------- FSM ----------------
class LotCreation(StatesGroup):
    name = State()
    description = State()
    price = State()
    photo = State()
    confirm = State()

def format_price_rub(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " руб."

def parse_price_to_int(text: str):
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None

# ---------------- Меню Лоты ----------------
@router.callback_query(F.data == "lots")
async def lots_menu(call: CallbackQuery):
    try:
        await call.message.delete()
    except:
        pass

    await call.message.answer_photo(
        photo=START_PHOTO,
        caption="📦 <b>Раздел лотов:</b>\n\nВыберите действие:",
        reply_markup=lots_menu_kb
    )

# ---------------- Создание ----------------
@router.callback_query(F.data == "create_lot")
async def start_lot_creation(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    try:
        await call.message.delete()
    except:
        pass

    msg = await call.message.answer("🏷️ <b>Введите название лота:</b>", reply_markup=back_kb())
    await state.set_state(LotCreation.name)
    await state.update_data(last_msg=msg.message_id)

@router.message(LotCreation.name)
async def set_name(msg: Message, state: FSMContext):
    await msg.delete()
    data = await state.get_data()
    if "last_msg" in data:
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except:
            pass
    await state.update_data(name=msg.text.strip())
    new_msg = await msg.answer("📝 <b>Введите описание лота:</b>", reply_markup=back_kb())
    await state.set_state(LotCreation.description)
    await state.update_data(last_msg=new_msg.message_id)

@router.message(LotCreation.description)
async def set_description(msg: Message, state: FSMContext):
    await msg.delete()
    data = await state.get_data()
    if "last_msg" in data:
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except:
            pass
    await state.update_data(description=msg.text.strip())
    new_msg = await msg.answer("💰 <b>Введите цену (число):</b>", reply_markup=back_kb())
    await state.set_state(LotCreation.price)
    await state.update_data(last_msg=new_msg.message_id)

@router.message(LotCreation.price)
async def set_price(msg: Message, state: FSMContext):
    price_int = parse_price_to_int(msg.text)
    await msg.delete()
    data = await state.get_data()
    if "last_msg" in data:
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except:
            pass
    if price_int is None:
        new_msg = await msg.answer("❌ Некорректная цена. Введите число:", reply_markup=back_kb())
        await state.update_data(last_msg=new_msg.message_id)
        return
    await state.update_data(price=price_int)
    new_msg = await msg.answer("📷 <b>Отправьте фото для лота:</b>", reply_markup=back_kb())
    await state.set_state(LotCreation.photo)
    await state.update_data(last_msg=new_msg.message_id)

@router.message(LotCreation.photo)
async def set_photo(msg: Message, state: FSMContext):
    if not msg.photo:
        await msg.delete()
        data = await state.get_data()
        if "last_msg" in data:
            try:
                await msg.bot.delete_message(msg.chat.id, data["last_msg"])
            except:
                pass
        new_msg = await msg.answer("❌ Нужно фото! Отправьте изображение:", reply_markup=back_kb())
        await state.update_data(last_msg=new_msg.message_id)
        return

    file_id = msg.photo[-1].file_id
    await msg.delete()
    data = await state.get_data()
    if "last_msg" in data:
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except:
            pass

    await state.update_data(photo=file_id)
    name = data.get("name", "")
    description = data.get("description", "")
    price = format_price_rub(data.get("price", 0))

    caption = f"📦 <b>{html.escape(name)}</b>\n\n{html.escape(description)}\n\n💰 <b>{price}</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Опубликовать", callback_data="publish_lot")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="lots")]
    ])
    preview_msg = await msg.answer_photo(photo=file_id, caption=caption, reply_markup=kb)
    await state.set_state(LotCreation.confirm)
    await state.update_data(last_msg=preview_msg.message_id)

# ---------------- Publish ----------------
@router.callback_query(F.data == "publish_lot")
async def publish_lot(call: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession):
    data = await state.get_data()
    if not data:
        await call.answer("⚠ Ошибка: данные не найдены", show_alert=True)
        return

    # найдём автора
    res = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    author = res.scalars().first()

    lot = Lot(
        name=data["name"],
        description=data["description"],
        price=int(data["price"]),
        photo=data["photo"],
        is_active=True,
        created_by=author.id if author else None
    )
    session.add(lot)
    await session.commit()
    await session.refresh(lot)
    log.info("Lot published: id=%s, name=%s, author_tg=%s", lot.id, lot.name, call.from_user.id)

    caption = (
        f"🟢 <b>Лот ID: {lot.id}</b>\n\n"
        f"📦 {html.escape(lot.name)}\n\n"
        f"{html.escape(lot.description)}\n\n"
        f"💰 <b>{format_price_rub(lot.price)}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_lot:{lot.id}")],
        [InlineKeyboardButton(text="🚚 Купить с доставкой", callback_data=f"buy_lot_delivery:{lot.id}")]
    ])
    msg_group = await bot.send_photo(chat_id=GROUP_ID, photo=lot.photo, caption=caption, reply_markup=kb)

    lot.message_id = msg_group.message_id
    await session.commit()

    await state.clear()
    await call.answer("✅ Лот опубликован", show_alert=True)
    await lots_menu(call)

# ---------------- Список лотов ----------------
@router.callback_query(F.data == "admin_lots")
async def list_lots(call: CallbackQuery, session: AsyncSession):
    res = await session.execute(select(Lot))
    lots = res.scalars().all()

    if not lots:
        try:
            await call.message.delete()
        except:
            pass
        await call.message.answer_photo(
            photo=START_PHOTO,
            caption="📋 Список лотов пуст",
            reply_markup=lots_menu_kb
        )
        return

    kb_rows = []
    for lot in lots:
        status = "🟢" if lot.is_active else "🔴"
        link = f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}" if lot.message_id else None
        left_text = (
            f"{status} id-{lot.id} | {lot.name[:20]}\n"
            f"💰 {format_price_rub(lot.price)}"
        )
        left_btn = InlineKeyboardButton(text=left_text, url=link if link else None)
        right_btn = InlineKeyboardButton(text="🔄 Поменять статус", callback_data=f"toggle_status:{lot.id}")
        kb_rows.append([left_btn, right_btn])

    kb_rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="lots")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    try:
        await call.message.delete()
    except:
        pass
    await call.message.answer_photo(
        photo=START_PHOTO,
        caption="📋 <b>Список лотов:</b>\n\nЗдесь вы можете управлять статусами:",
        reply_markup=kb
    )

# ---------------- Смена статуса ----------------
@router.callback_query(F.data.startswith("toggle_status:"))
async def toggle_status(call: CallbackQuery, session: AsyncSession, bot: Bot):
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)

    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True)
        return

    lot.is_active = not lot.is_active
    lot.status = "active" if lot.is_active else "archived"
    await session.commit()
    log.info("Lot status toggled: id=%s, is_active=%s", lot.id, lot.is_active)

    if lot.message_id:
        status_emoji = "🟢" if lot.is_active else "🔴"
        caption = (
            f"{status_emoji} <b>Лот ID: {lot.id}</b>\n\n"
            f"📦 {html.escape(lot.name)}\n\n"
            f"{html.escape(lot.description)}\n\n"
            f"💰 <b>{format_price_rub(lot.price)}</b>"
        )
        try:
            await bot.edit_message_caption(chat_id=GROUP_ID, message_id=lot.message_id, caption=caption)
        except Exception as e:
            log.warning("Can't edit group message for lot %s: %s", lot.id, e)

    await call.answer("✅ Статус изменён")
    await list_lots(call, session)
