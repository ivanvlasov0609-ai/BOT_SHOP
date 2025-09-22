import logging
import html
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import GROUP_ID, PHOTOS
from db import Lot
from keyboards.inline import lots_menu_kb
from handlers.lots.utils import format_price_rub, refresh_lot_keyboard

router = Router()
log = logging.getLogger(__name__)

# кэш базовой ссылки на группу
_GROUP_BASE_LINK: Optional[str] = None


async def _get_group_base_link(bot: Bot) -> str:
    """Публичная: https://t.me/<username> ; Приватная: https://t.me/c/<abs_id>"""
    global _GROUP_BASE_LINK
    if _GROUP_BASE_LINK:
        return _GROUP_BASE_LINK

    try:
        chat = await bot.get_chat(GROUP_ID)
        username = getattr(chat, "username", None)
        if username:
            _GROUP_BASE_LINK = f"https://t.me/{username}"
        else:
            gid = str(GROUP_ID)
            _GROUP_BASE_LINK = f"https://t.me/c/{gid[4:]}" if gid.startswith("-100") else f"https://t.me/c/{abs(int(GROUP_ID))}"
    except Exception as e:
        log.warning("Can't fetch chat username for GROUP_ID=%s: %s", GROUP_ID, e)
        gid = str(GROUP_ID)
        _GROUP_BASE_LINK = f"https://t.me/c/{gid[4:]}" if gid.startswith("-100") else f"https://t.me/c/{abs(int(GROUP_ID))}"
    return _GROUP_BASE_LINK


async def _post_link(bot: Bot, message_id: int | None) -> str | None:
    if not message_id:
        return None
    base = await _get_group_base_link(bot)
    return f"{base}/{message_id}"


@router.callback_query(F.data == "admin_lots")
async def list_lots(call: CallbackQuery, session: AsyncSession):
    """Админский список лотов с возможностью открыть пост, поменять статус и удалить лот."""
    await call.answer()
    res = await session.execute(select(Lot))
    lots = res.scalars().all()

    if not lots:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer_photo(
            photo=FSInputFile(PHOTOS["lots_panel"]),
            caption="📋 Список лотов пуст",
            reply_markup=lots_menu_kb
        )
        return

    kb_rows = []
    for lot in lots:
        status = "🟢" if lot.is_active else "🔴"
        link = await _post_link(call.bot, lot.message_id)

        left_text = (
            f"{status} id-{lot.id} | {lot.name[:20]}\n"
            f"💰 {format_price_rub(lot.price)}"
        )

        if link:
            left_btn = InlineKeyboardButton(text=left_text, url=link)
        else:
            left_btn = InlineKeyboardButton(text=left_text, callback_data=f"noop_lot:{lot.id}")

        toggle_btn = InlineKeyboardButton(text="🔄 Поменять статус", callback_data=f"toggle_status:{lot.id}")
        delete_btn = InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_lot:{lot.id}")
        kb_rows.append([left_btn, toggle_btn, delete_btn])

    kb_rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="lots")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_photo(
        photo=FSInputFile(PHOTOS["lots_panel"]),
        caption="📋 <b>Список лотов:</b>\n\nЗдесь вы можете управлять статусами и удалять лоты:",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("toggle_status:"))
async def toggle_status(call: CallbackQuery, session: AsyncSession, bot: Bot):
    """Переключение статуса лота + обновление поста и клавиатуры в группе."""
    await call.answer()
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
        except Exception:
            try:
                await bot.edit_message_text(chat_id=GROUP_ID, message_id=lot.message_id, text=caption)
            except Exception as e:
                log.warning("Can't edit group message for lot %s: %s", lot.id, e)

    await refresh_lot_keyboard(bot, lot)
    await list_lots(call, session)


@router.callback_query(F.data.startswith("delete_lot:"))
async def delete_lot_confirm(call: CallbackQuery, session: AsyncSession):
    """Подтверждение удаления лота."""
    await call.answer()
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)
    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True)
        return

    caption = (
        f"⚠️ <b>Удалить лот ID {lot.id}?</b>\n\n"
        f"📦 {html.escape(lot.name)}\n"
        f"💰 {format_price_rub(lot.price)}\n\n"
        f"Действие необратимо."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_lot:{lot.id}")],
        [InlineKeyboardButton(text="↩️ Отмена", callback_data="admin_lots")]
    ])

    try:
        await call.message.edit_caption(caption=caption, reply_markup=kb)
    except Exception:
        try:
            await call.message.delete()
        except Exception:
            pass
        from aiogram.types import FSInputFile
        await call.message.answer_photo(FSInputFile(PHOTOS["lots_panel"]), caption=caption, reply_markup=kb)


@router.callback_query(F.data.startswith("confirm_delete_lot:"))
async def delete_lot_apply(call: CallbackQuery, session: AsyncSession, bot: Bot):
    """Удаляем лот из БД и пост в группе (если был)."""
    await call.answer()
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)
    if not lot:
        await call.answer("❌ Лот уже удалён", show_alert=True)
        return

    # удаляем пост в группе
    if lot.message_id:
        try:
            await bot.delete_message(GROUP_ID, lot.message_id)
        except TelegramBadRequest:
            pass  # уже удалён — норм

    await session.delete(lot)
    await session.commit()
    log.info("Lot deleted: id=%s", lot_id)

    await call.answer("✅ Лот удалён")
    await list_lots(call, session)


@router.callback_query(F.data.startswith("noop_lot:"))
async def noop_lot(call: CallbackQuery):
    """Кнопка-заглушка, если у лота нет ссылки на пост."""
    await call.answer("Для этого лота ещё нет поста в группе.", show_alert=True)
