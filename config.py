import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
START_PHOTO = "image/start_panel.png"

START_MESSAGE_CLIENT = os.getenv("START_MESSAGE_CLIENT", "👋 Добро пожаловать!")
START_MESSAGE_ADMIN = os.getenv("START_MESSAGE_ADMIN", "👋 Привет, админ!")
PHOTOS = {
    "start": "5352896025829964668.jpg",  # одно фото для всех при /start
    # Админ-панель
    "admin_panel": "image/admin_panel.png",
    "lots_panel": "image/lots_panel.png",
    "requests_panel": "image/requests_panel.png",
}