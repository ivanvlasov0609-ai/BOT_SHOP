from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_lots_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить лот", callback_data="lot_create")],
        [InlineKeyboardButton(text="✏ Редактировать лот", callback_data="lot_edit_1")],  # пример
    ])
