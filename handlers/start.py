import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

# Импортируем настройки и клавиатуры
from config import ADMINS, START_PHOTO, START_MESSAGE_CLIENT, START_MESSAGE_ADMIN, PHOTOS
from keyboards.inline import client_kb, build_admin_main_kb, build_admin_panel_kb, admin_reply_kb
from db import User, Request, AdminUIState
from aiogram.types import FSInputFile

BOT_VERSION = "v1.0.0"
SUPPORT_TAG = "@IvanKuvshinow"

router = Router()
log = logging.getLogger(__name__)


# ===============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===============================

async def _pending_count(session: AsyncSession) -> int:
    """
    Считает количество заявок со статусом 'pending'.
    Возвращает число.
    """
    q = await session.execute(
        select(func.count(Request.id)).where(Request.status == "pending")
    )
    return int(q.scalar() or 0)


async def _set_admin_menu_state(session: AsyncSession, admin_user_id: int, msg_id: int):
    """
    Записывает в таблицу AdminUIState id последнего сообщения меню админа.
    Нужно для того, чтобы знать, какое сообщение обновлять в будущем.
    """
    q = await session.execute(
        select(AdminUIState).where(AdminUIState.admin_user_id == admin_user_id)
    )
    row = q.scalars().first()
    if not row:
        # если записи нет — создаём новую
        row = AdminUIState(admin_user_id=admin_user_id, last_menu_message_id=msg_id)
        session.add(row)
    else:
        # если запись есть — обновляем id сообщения
        row.last_menu_message_id = msg_id
    await session.commit()


# ===============================
# ХЕНДЛЕРЫ
# ===============================

@router.message(F.text == "/start")
async def start_cmd(msg: Message, session: AsyncSession):
    """
    Обрабатывает команду /start.
    - Если пользователь новый — создаёт запись в БД.
    - Если админ → сразу открывает админ-панель.
    - Если клиент → панель клиента.
    """
    user_id = msg.from_user.id

    # Проверяем, есть ли пользователь в базе
    res = await session.execute(select(User).where(User.tg_id == user_id))
    user = res.scalars().first()

    if not user:
        # Создаём нового пользователя
        user = User(
            tg_id=user_id,
            username=msg.from_user.username,
            full_name=msg.from_user.full_name,
            is_admin=(user_id in ADMINS)  # если его id есть в ADMINS → админ
        )
        session.add(user)
        await session.commit()
    else:
        # Обновляем данные существующего пользователя
        user.username = msg.from_user.username
        user.full_name = msg.from_user.full_name
        user.is_admin = (user_id in ADMINS)
        await session.commit()

    if user.is_admin:
        # === Админ ===
        pending = await _pending_count(session)  # считаем новые заявки
        # Отправляем фото + клавиатуру админ-панели
        m = await msg.answer_photo(
            photo=FSInputFile(PHOTOS["admin_panel"]),
            caption="⚙ Панель администратора:\nВыберите раздел:",
            reply_markup=build_admin_panel_kb(pending)
        )
        # Запоминаем id сообщения в БД
        await _set_admin_menu_state(session, user.id, m.message_id)
    else:
        # === Клиент ===
        await msg.answer_photo(
            photo=FSInputFile(START_PHOTO),
            caption=START_MESSAGE_CLIENT,
            reply_markup=client_kb
        )


@router.callback_query(F.data == "open_admin_panel")
async def open_admin_panel(call: CallbackQuery, session: AsyncSession):
    """
    Открывает админ-панель (по кнопке 'Открыть админ-панель').
    Теперь редактируем сообщение вместо удаления и нового.
    """
    pending = await _pending_count(session)
    await call.message.edit_media(
        media=InputMediaPhoto(
            media=FSInputFile(PHOTOS["admin_panel"]),
            caption="⚙ Панель администратора:\nВыберите раздел:"
        ),
        reply_markup=build_admin_panel_kb(pending)
    )


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery, session: AsyncSession):
    """
    Возвращает из клиентской панели обратно в админ-панель.
    Через edit_media.
    """
    pending = await _pending_count(session)

    await call.message.edit_media(
        media=InputMediaPhoto(
            media=FSInputFile(PHOTOS["admin_panel"]),
            caption="⚙ Панель администратора:\nВыберите раздел:"
        ),
        reply_markup=build_admin_panel_kb(pending)
    )

    # сохраняем id сообщения
    res = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin = res.scalars().first()
    if admin:
        await _set_admin_menu_state(session, admin.id, call.message.message_id)


@router.callback_query(F.data == "back_to_main")
async def back_to_main(call: CallbackQuery, session: AsyncSession):
    """
    Возвращает админа в главное меню (не панель, а стартовый экран).
    Через edit_media.
    """
    await call.message.edit_media(
        media=InputMediaPhoto(
            media=FSInputFile(START_PHOTO),
            caption=START_MESSAGE_ADMIN
        ),
        reply_markup=build_admin_main_kb()
    )
