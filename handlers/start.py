import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from config import ADMINS, START_PHOTO, START_MESSAGE_CLIENT, START_MESSAGE_ADMIN, PHOTOS
from keyboards.inline import client_kb, build_admin_main_kb, build_admin_panel_kb
from db import User, Request, AdminUIState
from aiogram.types import FSInputFile
from keyboards.inline import admin_reply_kb
BOT_VERSION = "v1.0.0"
SUPPORT_TAG = "@IvanKuvshinow"
router = Router()
log = logging.getLogger(__name__)

async def _pending_count(session: AsyncSession) -> int:
    q = await session.execute(select(func.count(Request.id)).where(Request.status == "pending"))
    return int(q.scalar() or 0)
async def _set_admin_menu_state(session: AsyncSession, admin_user_id: int, msg_id: int):
    q = await session.execute(select(AdminUIState).where(AdminUIState.admin_user_id == admin_user_id))
    row = q.scalars().first()
    if not row:
        row = AdminUIState(admin_user_id=admin_user_id, last_menu_message_id=msg_id)
        session.add(row)
    else:
        row.last_menu_message_id = msg_id
    await session.commit()
@router.message(F.text == "/start")
async def start_cmd(msg: Message, session: AsyncSession):
    user_id = msg.from_user.id
    res = await session.execute(select(User).where(User.tg_id == user_id))
    user = res.scalars().first()
    if not user:
        user = User(
            tg_id=user_id,
            username=msg.from_user.username,
            full_name=msg.from_user.full_name,
            is_admin=(user_id in ADMINS)
        )
        session.add(user); await session.commit()
    else:
        user.username = msg.from_user.username
        user.full_name = msg.from_user.full_name
        user.is_admin = (user_id in ADMINS)
        await session.commit()
    if user.is_admin:
        await msg.answer(f"🤖 Версия бота: <b>{BOT_VERSION}</b>\n"
                         f"🛠 Техническая поддержка: {SUPPORT_TAG}", reply_markup=admin_reply_kb)
        m = await msg.answer_photo(
            photo=FSInputFile(START_PHOTO),
            caption=START_MESSAGE_ADMIN,
            reply_markup=build_admin_main_kb()
        )
        # Отправляем клавиатуру (ReplyKeyboard)
        await _set_admin_menu_state(session, user.id, m.message_id)

    else:
        await msg.answer_photo(
            photo=FSInputFile(START_PHOTO),
            caption=START_MESSAGE_CLIENT,
            reply_markup=client_kb
        )

@router.callback_query(F.data == "open_admin_panel")
async def open_admin_panel(call: CallbackQuery, session: AsyncSession):
    pending = await _pending_count(session)
    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_photo(
        photo=FSInputFile(PHOTOS["admin_panel"]),   # ← используем отдельное фото
        caption="⚙ Панель администратора:\nВыберите раздел:",
        reply_markup=build_admin_panel_kb(pending)
    )

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery, session: AsyncSession):
    try:
        await call.message.delete()
    except:
        pass
    pending = await _pending_count(session)
    m = await call.message.answer_photo(
        photo=FSInputFile(PHOTOS["admin_panel"]),   # ← тоже отдельное фото
        caption="⚙ Панель администратора:\nВыберите раздел:",
        reply_markup=build_admin_panel_kb(pending)
    )
    res = await session.execute(select(User).where(User.tg_id == call.from_user.id))
    admin = res.scalars().first()
    if admin:
        await _set_admin_menu_state(session, admin.id, m.message_id)

@router.callback_query(F.data == "back_to_main")
async def back_to_main(call: CallbackQuery, session: AsyncSession):
    m = await call.message.edit_caption(
        caption=START_MESSAGE_ADMIN,
        reply_markup=build_admin_main_kb()
    )
@router.message(F.text == "🏠 Вернуться в главное меню")
@router.message(F.text == "🏠 Вернуться в меню")
async def back_to_main_menu(msg: Message, session: AsyncSession):
    pass
