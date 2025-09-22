from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from db import Request


# ===============================
# 🔹 Клиентское меню
# ===============================
client_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📂 Каталог", callback_data="catalog")],
    [InlineKeyboardButton(text="🎟 Промокод", callback_data="promocode")],
    [InlineKeyboardButton(text="🎁 Участвовать в розыгрыше", callback_data="raffle")],
    [InlineKeyboardButton(text="🕹 Купить подписку PlayStation", callback_data="buy_ps")],
])

# ===============================
# 🔹 Главное меню админа
# ===============================
def build_admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="promocode")],
        [InlineKeyboardButton(text="🎁 Участвовать в розыгрыше", callback_data="raffle")],
        [InlineKeyboardButton(text="🕹 Купить подписку PlayStation", callback_data="buy_ps")],
        [InlineKeyboardButton(text="⚙ Панель администратора", callback_data="open_admin_panel")],
    ])

# ===============================
# 🔹 Панель администратора
# ===============================
def build_admin_panel_kb(pending_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Каталог", callback_data="admin_catalog")],
        [InlineKeyboardButton(text=f"📑 Заявки (Новых: {pending_count})", callback_data="requests")],
        [InlineKeyboardButton(text="📦 Лоты", callback_data="lots")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promocodes")],
        [InlineKeyboardButton(text="🎁 Розыгрыши", callback_data="admin_raffle")],
        [InlineKeyboardButton(text="🧹 Очистить заявки", callback_data="requests_cleanup")],
        [InlineKeyboardButton(text="⚙ Панель клиента", callback_data="back_to_main")],
    ])

# ===============================
# 🔹 Меню «Лоты»
# ===============================
lots_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Создать лот", callback_data="create_lot")],
    [InlineKeyboardButton(text="📋 Список лотов", callback_data="admin_lots")],
    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")]
])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="lots")]
    ])

# ===============================
# 🔹 Панель «Заявки»
# ===============================
def requests_root_kb(counts: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🟢 Новые ({counts['pending']})", callback_data="req_tab:pending:0")],
        [InlineKeyboardButton(text=f"🟠 В работе ({counts['processing']})", callback_data="req_tab:processing:0")],
        [InlineKeyboardButton(text=f"🔴 Закрытые ({counts['done']})", callback_data="req_tab:done:0")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_admin")],
    ])

def list_requests_kb(entries, status: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Строит список заявок + навигацию по страницам
    entries: [(id, title), ...]
    """
    rows = []
    for r_id, title in entries:
        rows.append([InlineKeyboardButton(text=title, callback_data=f"req_open:{r_id}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⟨ Назад", callback_data=f"req_tab:{status}:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд ⟩", callback_data=f"req_tab:{status}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅ К разделам", callback_data="requests")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def combined_kb(req: Request, user_tg_id: int | None, lot_link: str | None) -> InlineKeyboardMarkup:
    """
    Кнопки в карточке заявки
    """
    rows = []

    # управление статусом
    if req.status == "pending":
        rows.append([InlineKeyboardButton(text="🛠 Взять в работу", callback_data=f"req_take:{req.id}")])
    elif req.status == "processing":
        rows.append([InlineKeyboardButton(text="✅ Закрыть заявку", callback_data=f"req_close:{req.id}")])
    elif req.status == "done":
        rows.append([InlineKeyboardButton(text="🔄 Взять в работу снова", callback_data=f"req_take:{req.id}")])

    # лот
    if req.target_type == "lot":
        rows.append([InlineKeyboardButton(text="🔁 Сменить статус лота", callback_data=f"req_toggle_lot:{req.id}")])
        if lot_link:
            rows.append([InlineKeyboardButton(text="📦 Открыть лот", url=lot_link)])

    # клиент
    if user_tg_id:
        rows.append([InlineKeyboardButton(text="👤 Открыть клиента", url=f"tg://user?id={user_tg_id}")])

    # сообщение клиенту
    if req.status != "done":
        rows.append([InlineKeyboardButton(text="✉️ Написать клиенту", callback_data=f"req_msg:{req.id}")])

    # назад
    rows.append([InlineKeyboardButton(text="⬅ К разделам", callback_data="requests")])

    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===============================
# 🔹 Reply-клавиатура для админа
# ===============================
admin_reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Вернуться в меню")],
    ],
    resize_keyboard=True
)
