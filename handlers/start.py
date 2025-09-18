import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import ADMINS, START_PHOTO, START_MESSAGE_CLIENT, START_MESSAGE_ADMIN
from keyboards.inline import client_kb, admin_main_kb, build_admin_panel_kb
from db import User

router = Router()
log = logging.getLogger(__name__)

@router.message(F.text == "/start")
async def start_cmd(msg: Message, session: AsyncSession):
    user_id = msg.from_user.id
    for i in range(msg.message_id, msg.message_id - 30, -1):
        try:
            await msg.bot.delete_message(chat_id=msg.chat.id, message_id=i)
        except:
            pass

    res = await session.execute(select(User).where(User.tg_id == user_id))
    user = res.scalars().first()
    if not user:
        user = User(
            tg_id=user_id,
            username=msg.from_user.username,
            full_name=msg.from_user.full_name,
            is_admin=(user_id in ADMINS)
        )
        session.add(user)
    else:
        user.username = msg.from_user.username
        user.full_name = msg.from_user.full_name
        user.is_admin = (user_id in ADMINS)
    await session.commit()

    if user.is_admin:
        await msg.answer_photo(START_PHOTO, caption=START_MESSAGE_ADMIN, reply_markup=admin_main_kb)
    else:
        await msg.answer_photo(START_PHOTO, caption=START_MESSAGE_CLIENT, reply_markup=client_kb)

@router.callback_query(F.data == "open_admin_panel")
async def open_admin(call: CallbackQuery):
    await call.message.edit_caption(
        caption="⚙ Панель администратора:\nВыберите раздел:",
        reply_markup=build_admin_panel_kb()
    )

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    try:
        await call.message.delete()
    except:
        pass
    await call.message.answer_photo(
        photo=START_PHOTO,
        caption="⚙ Панель администратора:\nВыберите раздел:",
        reply_markup=build_admin_panel_kb()
    )

@router.callback_query(F.data == "back_to_main")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_caption(
        caption=START_MESSAGE_ADMIN,
        reply_markup=admin_main_kb
    )
