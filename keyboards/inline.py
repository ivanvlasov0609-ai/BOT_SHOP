from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Кнопки для клиента
client_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📂 Каталог", callback_data="catalog")],
    [InlineKeyboardButton(text="🎟 Промокод", callback_data="promocode")],
    [InlineKeyboardButton(text="🎁 Участвовать в розыгрыше", callback_data="raffle")],
    [InlineKeyboardButton(text="🕹 Купить подписку PlayStation", callback_data="buy_ps")],
])

# Кнопки для админа (главное меню)
admin_main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📂 Каталог", callback_data="catalog")],
    [InlineKeyboardButton(text="🎟 Промокод", callback_data="promocode")],
    [InlineKeyboardButton(text="🎁 Участвовать в розыгрыше", callback_data="raffle")],
    [InlineKeyboardButton(text="🕹 Купить подписку PlayStation", callback_data="buy_ps")],
    [InlineKeyboardButton(text="⚙ Панель администратора", callback_data="open_admin_panel")],
])

# Админская панель управления
admin_panel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📂 Каталог", callback_data="admin_catalog")],
    [InlineKeyboardButton(text="📦 Лоты", callback_data="lots")],
    [InlineKeyboardButton(text="📑 Заявки", callback_data="requests")],
    [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promocodes")],
    [InlineKeyboardButton(text="🎁 Розыгрыши", callback_data="admin_raffle")],
    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")],
])
# Меню Лоты
lots_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Создать лот", callback_data="create_lot")],
    [InlineKeyboardButton(text="📋 Список лотов", callback_data="admin_lots")],
    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")]
])
def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="lots")]
    ])
