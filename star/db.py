from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, relationship
from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any
from datetime import datetime

# ---------- SQLAlchemy Base ----------
Base = declarative_base()

# ---------- Модели ----------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)

    requests = relationship("Request", back_populates="user")
    notifications = relationship("AdminNotification", back_populates="admin_user")


class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    price = Column(Integer)
    photo = Column(String)
    is_active = Column(Boolean, default=True)
    message_id = Column(BigInteger, nullable=True)


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    target_type = Column(String)  # "lot" или "product"
    target_id = Column(Integer)
    prepayment_amount = Column(Integer)
    total_amount = Column(Integer)
    status = Column(String, default="pending")  # pending / processing / done
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    taken_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    taken_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="requests")


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"))
    request_id = Column(Integer, ForeignKey("requests.id"))
    tg_message_id = Column(BigInteger, nullable=True)
    is_hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin_user = relationship("User", back_populates="notifications")


class AdminUIState(Base):
    __tablename__ = "admin_ui_state"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # id последнего сообщения главного меню
    last_menu_message_id = Column(BigInteger, nullable=True)

    # id последнего сообщения панели заявок (🔥 новое поле)
    last_requests_message_id = Column(BigInteger, nullable=True)


class Raffle(Base):
    __tablename__ = "raffles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    start_at = Column(DateTime, default=datetime.utcnow)
    end_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    participants = relationship("RaffleParticipant", back_populates="raffle")


class RaffleParticipant(Base):
    __tablename__ = "raffle_participants"

    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"))
    user_id = Column(BigInteger)

    raffle = relationship("Raffle", back_populates="participants")

# ---------- Настройка БД ----------

DATABASE_URL = "sqlite+aiosqlite:///./bot.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ---------- Middleware для сессий ----------

class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory):
        super().__init__()
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)

def get_session_middleware():
    return DBSessionMiddleware(async_session)
