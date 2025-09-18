from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Клиентское меню (заявок тут нет)
client_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📂 Каталог", callback_data="catalog")],
    [InlineKeyboardButton(text="🎟 Промокод", callback_data="promocode")],
    [InlineKeyboardButton(text="🎁 Участвовать в розыгрыше", callback_data="raffle")],
    [InlineKeyboardButton(text="🕹 Купить подписку PlayStation", callback_data="buy_ps")],
])

# Главное меню админа (кнопка входа в панель)
def build_admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="promocode")],
        [InlineKeyboardButton(text="🎁 Участвовать в розыгрыше", callback_data="raffle")],
        [InlineKeyboardButton(text="🕹 Купить подписку PlayStation", callback_data="buy_ps")],
        [InlineKeyboardButton(text="⚙ Панель администратора", callback_data="open_admin_panel")],
    ])

# Панель админа — показываем кол-во НОВЫХ заявок
def build_admin_panel_kb(pending_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Каталог", callback_data="admin_catalog")],
        [InlineKeyboardButton(text=f"📑 Заявки (Новых: {pending_count})", callback_data="requests")],
        [InlineKeyboardButton(text="📦 Лоты", callback_data="lots")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promocodes")],
        [InlineKeyboardButton(text="🎁 Розыгрыши", callback_data="admin_raffle")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")],
    ])

# Меню «Лоты»
lots_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Создать лот", callback_data="create_lot")],
    [InlineKeyboardButton(text="📋 Список лотов", callback_data="admin_lots")],
    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")]
])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="lots")]
    ])
