# handlers/lots/create.py
import logging
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
from keyboards.inline import back_kb
from handlers.lots.utils import format_price_rub, parse_price_to_int, build_buy_kb
from handlers.lots.menu import lots_menu

router = Router()
log = logging.getLogger(__name__)


# ---------------- FSM ----------------
class LotCreation(StatesGroup):
    name = State()
    description = State()
    price = State()
    photo = State()
    confirm = State()


# ---------------- Старт создания ----------------
@router.callback_query(F.data == "create_lot")
async def start_lot_creation(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    try:
        await call.message.delete()
    except Exception:
        pass

    msg = await call.message.answer("🏷️ <b>Введите название лота:</b>", reply_markup=back_kb())
    await state.set_state(LotCreation.name)
    await state.update_data(last_msg=msg.message_id)


@router.message(LotCreation.name)
async def set_name(msg: Message, state: FSMContext):
    await msg.delete()
    data = await state.get_data()
    if data.get("last_msg"):
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except Exception:
            pass

    await state.update_data(name=msg.text.strip())
    new_msg = await msg.answer("📝 <b>Введите описание лота:</b>", reply_markup=back_kb())
    await state.set_state(LotCreation.description)
    await state.update_data(last_msg=new_msg.message_id)


@router.message(LotCreation.description)
async def set_description(msg: Message, state: FSMContext):
    await msg.delete()
    data = await state.get_data()
    if data.get("last_msg"):
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except Exception:
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
    if data.get("last_msg"):
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except Exception:
            pass

    if price_int is None:
        new_msg = await msg.answer("❌ Некорректная цена. Введите число:", reply_markup=back_kb())
        await state.update_data(last_msg=new_msg.message_id)
        return

    await state.update_data(price=price_int, preview_shown=False, album_mg_id=None, photo=None)
    new_msg = await msg.answer("📷 <b>Отправьте ОДНО фото лота</b>", reply_markup=back_kb())
    await state.set_state(LotCreation.photo)
    await state.update_data(last_msg=new_msg.message_id)


@router.message(LotCreation.photo)
async def set_photo(msg: Message, state: FSMContext):
    """
    Принимаем только ПЕРВОЕ фото.
    - Если прилетело несколько (альбом/несколько сообщений) — игнорируем всё, что позже.
    """
    # если это не фото — игнор
    if not msg.photo:
        await msg.delete()
        return

    data = await state.get_data()

    # уже приняли фото/показали превью — игнорируем любые последующие кадры
    if data.get("photo") or data.get("preview_shown"):
        await msg.delete()
        return

    # если это альбом, фиксируем его id и всё равно берём ТОЛЬКО первый кадр
    if msg.media_group_id is not None:
        mg_id = str(msg.media_group_id)
        if data.get("album_mg_id") and data.get("album_mg_id") != mg_id:
            # другой альбом — игнор
            await msg.delete()
            return
        # если первый кадр уже принят, выше мы уже вышли по photo/preview_shown
        await state.update_data(album_mg_id=mg_id)

    file_id = msg.photo[-1].file_id
    await msg.delete()

    # удалим подсказку "Отправьте фото"
    if data.get("last_msg"):
        try:
            await msg.bot.delete_message(msg.chat.id, data["last_msg"])
        except Exception:
            pass

    # сохраняем единственное фото сразу, чтобы следующие кадры проигнорировались
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
    await state.update_data(last_msg=preview_msg.message_id, preview_shown=True)


# ---------------- Публикация ----------------
@router.callback_query(F.data == "publish_lot")
async def publish_lot(call: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    if not data:
        await call.answer("⚠ Ошибка: данные не найдены", show_alert=True)
        return

    # Автор (если есть)
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

    # одно фото в группу + кнопки покупки
    msg_group = await bot.send_photo(
        chat_id=GROUP_ID,
        photo=lot.photo,
        caption=caption,
        reply_markup=build_buy_kb(lot.id)
    )

    lot.message_id = msg_group.message_id
    await session.commit()

    await state.clear()
    await call.answer("✅ Лот опубликован", show_alert=True)
    await lots_menu(call)
