from sqlalchemy import (
    Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, Text
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, foreign
from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Request", back_populates="user")
class AdminUIState(Base):
    __tablename__ = "admin_ui_state"

    id = Column(Integer, primary_key=True)
    admin_user_id = Column(Integer, nullable=False)  # FK не обязательно
    last_menu_message_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
class Lot(Base):
    __tablename__ = "lots"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    price = Column(Integer)
    photo = Column(String)
    is_active = Column(Boolean, default=True)
    message_id = Column(BigInteger, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")
    updated_at = Column(DateTime)
    creator = relationship("User")
    requests = relationship(
        "Request",
        primaryjoin="and_(Lot.id==foreign(Request.target_id), Request.target_type=='lot')",
        viewonly=True
    )

class Raffle(Base):
    __tablename__ = "raffles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    start_at = Column(DateTime, default=datetime.utcnow)
    end_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rules = Column(Text, nullable=True)
    prize = Column(Text, nullable=True)
    updated_at = Column(DateTime)
    participants = relationship("RaffleParticipant", back_populates="raffle")
    creator = relationship("User")

class RaffleParticipant(Base):
    __tablename__ = "raffle_participants"
    id = Column(Integer, primary_key=True, index=True)
    raffle_id = Column(Integer, ForeignKey("raffles.id"))
    user_id = Column(BigInteger)
    raffle = relationship("Raffle", back_populates="participants")

class PromoCode(Base):
    __tablename__ = "promocodes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    benefit_type = Column(String, default="percent")
    benefit_value = Column(Integer, default=0)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, default="digital")
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    photo = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)
    requests = relationship(
        "Request",
        primaryjoin="and_(Product.id==foreign(Request.target_id), Request.target_type=='product')",
        viewonly=True
    )

class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_type = Column(String, nullable=False)   # 'lot' | 'product'
    target_id = Column(Integer, nullable=False)    # lots.id OR products.id
    promocode_id = Column(Integer, ForeignKey("promocodes.id"), nullable=True)
    prepayment_amount = Column(Integer, default=0)
    total_amount = Column(Integer, nullable=False)

    # Статусы: pending | processing | done
    status = Column(String, default="pending")
    details = Column(Text, nullable=True)

    # Новые поля для учёта исполнителя и времени
    taken_by_admin_id = Column(Integer, nullable=True)
    taken_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
    promocode = relationship("PromoCode")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="pending")
    provider = Column(String, nullable=True)
    txn_id = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AdminNotification(Base):
    """
    Что отправили как уведомление администратору (для «Скрыть» и восстановления через панель).
    """
    __tablename__ = "admin_notifications"
    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # наш users.id (не tg_id)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    tg_message_id = Column(BigInteger, nullable=True)  # id сообщения у админа (может быть удалён)
    is_hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

DATABASE_URL = "sqlite+aiosqlite:///./bot.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory):
        super().__init__()
        self.session_factory = session_factory

    async def __call__(self, handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]], event: Any, data: Dict[str, Any]) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)

def get_session_middleware():
    return DBSessionMiddleware(async_session)
