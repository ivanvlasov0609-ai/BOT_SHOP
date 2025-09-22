import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMedia
from config import GROUP_ID

def format_price_rub(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " руб."

def parse_price_to_int(text: str):
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None

def build_buy_kb(lot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_lot:{lot_id}")],
        [InlineKeyboardButton(text="🚚 Купить с доставкой", callback_data=f"buy_lot_delivery:{lot_id}")]
    ])

async def refresh_lot_keyboard(bot, lot) -> None:
    """
    Обновляет сообщение лота в группе:
    - меняет статус 🔴/🟢 в caption
    - обновляет inline-кнопки (или убирает их)
    """
    if not getattr(lot, "message_id", None):
        return

    # статус в начале
    status_icon = "🟢" if getattr(lot, "is_active", False) else "🔴"

    caption = (
        f"{status_icon} Лот ID: {lot.id}\n\n"
        f"📦 {lot.name}\n\n"
        f"{lot.description or ''}\n\n"
        f"💰 {format_price_rub(lot.price)}"
    )

    kb = build_buy_kb(lot.id) if getattr(lot, "is_active", False) else None


    media = InputMediaPhoto(media=lot.photo, caption=caption)
    await bot.edit_message_media(
        chat_id=GROUP_ID,
        message_id=lot.message_id,
        media=media,
        reply_markup=kb)
