from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from config import ADMINS, GROUP_ID
from db import Lot
from handlers.lots import format_price_rub  # используем готовую функцию форматирования

router = Router()


# ----------- Купить без доставки -----------
@router.callback_query(F.data.startswith("buy_lot:"))
async def client_buy_lot(call: CallbackQuery, session: AsyncSession):
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)

    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True)
        return

    # Ссылка на сообщение в группе (если опубликован)
    link = f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}" if lot.message_id else "—"

    # Сообщение админу
    for admin_id in ADMINS:
        await call.bot.send_message(
            chat_id=admin_id,
            text=(
                f"📢 <b>Новый заказ!</b>\n\n"
                f"👤 Пользователь: {call.from_user.full_name} (@{call.from_user.username})\n"
                f"🆔 Telegram ID: <code>{call.from_user.id}</code>\n\n"
                f"📦 Лот: <b>{lot.name}</b>\n"
                f"💰 Цена: {format_price_rub(lot.price)}\n"
                f"🚀 Способ: Самовывоз\n\n"
                f"🔗 <a href='{link}'>Перейти к объявлению</a>"
            ),
            disable_web_page_preview=True
        )

    await call.answer("✅ Заявка отправлена админу. С вами скоро свяжутся!")


# ----------- Купить с доставкой -----------
@router.callback_query(F.data.startswith("buy_lot_delivery:"))
async def client_buy_lot_delivery(call: CallbackQuery, session: AsyncSession):
    lot_id = int(call.data.split(":")[1])
    lot = await session.get(Lot, lot_id)

    if not lot:
        await call.answer("❌ Лот не найден", show_alert=True)
        return

    link = f"https://t.me/c/{str(GROUP_ID)[4:]}/{lot.message_id}" if lot.message_id else "—"

    for admin_id in ADMINS:
        await call.bot.send_message(
            chat_id=admin_id,
            text=(
                f"📢 <b>Новый заказ (с доставкой)!</b>\n\n"
                f"👤 Пользователь: {call.from_user.full_name} (@{call.from_user.username})\n"
                f"🆔 Telegram ID: <code>{call.from_user.id}</code>\n\n"
                f"📦 Лот: <b>{lot.name}</b>\n"
                f"💰 Цена: {format_price_rub(lot.price)}\n"
                f"🚚 Способ: Доставка\n\n"
                f"🔗 <a href='{link}'>Перейти к объявлению</a>"
            ),
            disable_web_page_preview=True
        )

    await call.answer("✅ Заявка с доставкой отправлена админу!")
