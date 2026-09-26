"""Shared coin-symbol normalization for alerts (chat + Mini App).

Both call sites used to carry their own copy of this function with a
real bug: "BTC" alone was checked with `coin.endswith(known_quotes)`,
and "BTC" trivially ends with itself, so a bare "BTC" was treated as
an already-complete pair and never got "USDT" appended - Binance then
rejects the bare symbol "BTC" as unknown ("BTC topilmadi"). The fix is
requiring a non-empty base portion before the quote suffix.
"""
from __future__ import annotations

_KNOWN_QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "TRY", "EUR", "BTC", "ETH")


def normalize_symbol(raw: str) -> str:
    """btc / BTC / BTCUSDT / BTC/USDT / BTC-USDT / BTC_USDT -> BTCUSDT
    ethbtc / ETH/BTC -> ETHBTC (kept as-is: a real BTC-quoted pair)."""
    coin = (raw or "").strip().upper()
    for sep in (" ", "/", "-", "_"):
        coin = coin.replace(sep, "")
    if not coin:
        return coin
    for quote in sorted(_KNOWN_QUOTES, key=len, reverse=True):
        if coin.endswith(quote) and len(coin) > len(quote):
            return coin
    return coin + "USDT"
