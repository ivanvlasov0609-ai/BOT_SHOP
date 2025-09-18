import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
START_PHOTO = os.getenv("START_PHOTO")

START_MESSAGE_CLIENT = os.getenv("START_MESSAGE_CLIENT", "👋 Добро пожаловать!")
START_MESSAGE_ADMIN = os.getenv("START_MESSAGE_ADMIN", "👋 Привет, админ!")
