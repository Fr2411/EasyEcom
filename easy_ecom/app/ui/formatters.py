from __future__ import annotations


def format_money(amount: float, currency_code: str, currency_symbol: str = "") -> str:
    marker = currency_symbol.strip() or currency_code.strip().upper() or "USD"
    return f"{marker} {amount:,.2f}"
