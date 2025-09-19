import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import GROUP_ID

def format_price_rub(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " руб."

def parse_price_to_int(text: str):
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None

def build_buy_kb(lot_id: int) -> InlineKeyboardMarkup:
    # тексты ровно как в твоём исходном файле
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_lot:{lot_id}")],
        [InlineKeyboardButton(text="🚚 Купить с доставкой", callback_data=f"buy_lot_delivery:{lot_id}")]
    ])

async def refresh_lot_keyboard(bot, lot) -> None:
    """
    Обновляет клавиатуру под сообщением лота в группе:
    - если lot.is_active == True -> показываем кнопки
    - если False -> убираем кнопки
    """
    if not getattr(lot, "message_id", None):
        return
    kb = build_buy_kb(lot.id) if getattr(lot, "is_active", False) else None
    try:
        await bot.edit_message_reply_markup(
            chat_id=GROUP_ID,
            message_id=lot.message_id,
            reply_markup=kb
        )
    except Exception:
        pass
