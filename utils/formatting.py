def format_price_rub(value: int | float) -> str:
    """Форматируем число как цену в рублях"""
    return f"{value:,.0f} руб.".replace(",", " ")