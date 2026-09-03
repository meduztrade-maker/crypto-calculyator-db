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
