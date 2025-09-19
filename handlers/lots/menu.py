import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from config import PHOTOS
from keyboards.inline import lots_menu_kb

router = Router()
log = logging.getLogger(__name__)

@router.callback_query(F.data == "lots")
async def lots_menu(call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer_photo(
        photo=FSInputFile(PHOTOS["lots_panel"]),
        caption="📦 <b>Раздел лотов:</b>\n\nВыберите действие:",
        reply_markup=lots_menu_kb,
    )
