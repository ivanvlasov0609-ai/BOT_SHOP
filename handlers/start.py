from aiogram import Router, F
from aiogram.types import Message, CallbackQuery,FSInputFile
from config import ADMINS, START_PHOTO, START_MESSAGE_CLIENT, START_MESSAGE_ADMIN
from keyboards.inline import client_kb, admin_main_kb, admin_panel_kb

router = Router()

@router.message(F.text == "/start")
async def start_cmd(msg: Message):
    user_id = msg.from_user.id
    for i in range(msg.message_id, msg.message_id - 50, -1):
        try:
            await msg.bot.delete_message(chat_id=msg.chat.id, message_id=i)
        except:
            pass
    if user_id in ADMINS:
        await msg.answer_photo(
            photo=START_PHOTO,
            caption=START_MESSAGE_ADMIN,
            reply_markup=admin_main_kb
        )
    else:
        await msg.answer_photo(
            photo=START_PHOTO,
            caption=START_MESSAGE_CLIENT,
            reply_markup=client_kb
        )
@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    """Возврат в панель администратора с фото и меню"""
    try:
        await call.message.delete()
    except:
        pass

    await call.message.answer_photo(
        photo=START_PHOTO,
        caption="⚙ Панель администратора:\nВыберите раздел:",
        reply_markup=admin_panel_kb
    )
@router.callback_query(F.data == "open_admin_panel")
async def open_admin(call: CallbackQuery):
    await call.message.edit_caption(
        caption="⚙ Панель администратора:\nВыберите раздел:",
        reply_markup=admin_panel_kb
    )

@router.callback_query(F.data == "back_to_main")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_caption(
        caption=START_MESSAGE_ADMIN,
        reply_markup=admin_main_kb
    )
@router.message(F.photo)
async def debug_photo(msg: Message):
    await msg.answer(f"file_id: {msg.photo[-1].file_id}")
