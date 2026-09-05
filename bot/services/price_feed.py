from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

import aiohttp

logger = logging.getLogger("meduz_bot")

_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class PriceLookupError(Exception):
    pass


async def get_price(symbol: str) -> Decimal:
    """Fetch a single symbol's current price. Used to validate a coin when creating an alert."""
    symbol = symbol.strip().upper()
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        async with http.get(_TICKER_URL, params={"symbol": symbol}) as resp:
            if resp.status != 200:
                raise PriceLookupError(f"{symbol} topilmadi (Binance'da mavjud emas)")
            data = await resp.json()
    try:
        return Decimal(data["price"])
    except (KeyError, InvalidOperation):
        raise PriceLookupError(f"{symbol} narxini olishda xatolik")


async def get_all_prices() -> dict[str, Decimal]:
    """
    Fetch every symbol's price in one request — used by the alert-checking background
    job so N active alerts cost one HTTP call, not N.
    """
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        async with http.get(_TICKER_URL) as resp:
            if resp.status != 200:
                logger.warning("Binance ticker fetch failed with status %s", resp.status)
                return {}
            data = await resp.json()

    prices: dict[str, Decimal] = {}
    for entry in data:
        try:
            prices[entry["symbol"]] = Decimal(entry["price"])
        except (KeyError, InvalidOperation):
            continue
    return prices


_KLINES_URL = "https://api.binance.com/api/v3/klines"


async def get_klines(symbol: str, interval: str = "15m", limit: int = 96) -> list[dict]:
    """
    Recent candles for a lightweight price chart — [{t: close_time_ms, c: close_price}, ...],
    oldest first. Used by the Mini App's alert detail chart.
    """
    symbol = symbol.strip().upper()
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        async with http.get(_KLINES_URL, params={"symbol": symbol, "interval": interval, "limit": str(limit)}) as resp:
            if resp.status != 200:
                raise PriceLookupError(f"{symbol} uchun narx tarixi topilmadi")
            data = await resp.json()

    out = []
    for row in data:
        try:
            out.append({"t": int(row[6]), "c": str(Decimal(row[4]))})  # close_time, close price
        except (IndexError, InvalidOperation):
            continue
    return out
