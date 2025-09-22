from datetime import datetime

RU_STATUS = {
    "pending":    ("🟢", "Новая"),
    "processing": ("🟠", "В работе"),
    "done":       ("🔴", "Закрыта"),
}

def s_icon(status: str) -> str:
    return RU_STATUS.get(status, ("⚪", ""))[0]

def s_badge(status: str) -> str:
    icon, name = RU_STATUS.get(status, ("⚪", status))
    return f"{icon} {name}"

def lot_status_dot(lot) -> str:
    return "🟢" if (lot and getattr(lot, "is_active", False)) else "🔴"

def fmt_dt_ru(dt: datetime | None) -> str:
    return dt.strftime("%d.%m.%Y %H:%M") if dt else "—"
