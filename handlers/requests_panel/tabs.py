import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from db import Request, Lot, Product
from config import PHOTOS
from handlers.lots.utils import format_price_rub
from handlers.requests_panel.utils import s_badge, s_icon
from keyboards.inline import list_requests_kb

router = Router()
log = logging.getLogger(__name__)

PAGE_SIZE = 10
TRIM_LEN = 48

def _entry_title(r: Request, name: str, price: int):
    if name and len(name) > TRIM_LEN:
        name = name[:TRIM_LEN - 1] + "…"
    return f"{s_icon(r.status)} #{r.id} • {name} • {format_price_rub(price)}"

@router.callback_query(F.data.startswith("req_tab:"))
async def open_requests_tab(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    parts = call.data.split(":")
    status = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    qcnt = await session.execute(select(func.count(Request.id)).where(Request.status == status))
    total = int(qcnt.scalar() or 0)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    offset = page * PAGE_SIZE
    res = await session.execute(
        select(Request)
        .where(Request.status == status)
        .order_by(Request.created_at.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    reqs = res.scalars().all()

    entries = []
    for r in reqs:
        name, price = "—", r.total_amount
        if r.target_type == "lot":
            lot = await session.get(Lot, r.target_id)
            if lot:
                name, price = lot.name, lot.price
        else:
            product = await session.get(Product, r.target_id)
            if product:
                name, price = product.name, product.price
        entries.append((r.id, _entry_title(r, name, price)))

    caption = f"📂 {s_badge(status)} заявки (стр. {page+1}/{total_pages}):"

    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_photo(
        photo=FSInputFile(PHOTOS["requests_panel"]),
        caption=caption,
        reply_markup=list_requests_kb(entries, status, page, total_pages)
    )
