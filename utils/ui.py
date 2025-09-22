from aiogram.types import Message, InlineKeyboardMarkup, InputMediaPhoto, FSInputFile
import os

async def update_panel(
    message: Message,
    photo: str,
    caption: str,
    keyboard: InlineKeyboardMarkup | None = None
):
    """
    Обновляет сообщение с фото и клавиатурой.
    Если photo — это путь к файлу, используем FSInputFile.
    Если это file_id, передаём как есть.
    """
    if os.path.exists(photo):
        media = InputMediaPhoto(media=FSInputFile(photo), caption=caption)
    else:
        media = InputMediaPhoto(media=photo, caption=caption)  # file_id

    await message.edit_media(media=media, reply_markup=keyboard)