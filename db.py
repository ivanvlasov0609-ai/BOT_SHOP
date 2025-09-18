from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, relationship
from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any
from datetime import datetime
import asyncio

# ---------- SQLAlchemy Base ----------
Base = declarative_base()

# ---------- Модели ----------

class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    price = Column(Integer)
    photo = Column(String)
    is_active = Column(Boolean, default=True)
    message_id = Column(BigInteger, nullable=True)


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

DATABASE_URL = "sqlite+aiosqlite:///./bot.db"  # Можно заменить на PostgreSQL, если нужно

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    """Создание таблиц"""
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
