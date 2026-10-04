from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

import aiohttp

logger = logging.getLogger("meduz_bot")

_TIMEOUT = aiohttp.ClientTimeout(total=10)
_SPOT_TICKER_URL = "https://data-api.binance.vision/api/v3/ticker/price"
_FUTURES_TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/price"
_BYBIT_TICKER_URL = "https://api.bybit.com/v5/market/tickers"
_MEXC_TICKER_URL = "https://contract.mexc.com/api/v1/contract/ticker"
_KLINES_URL = "https://data-api.binance.vision/api/v3/klines"

_QUOTE_SUFFIXES = ("USDT", "USDC", "BUSD", "FDUSD")


class PriceLookupError(Exception):
    pass


def _to_decimal(raw) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PriceLookupError(f"Narxni o'qib bo'lmadi: {raw!r}") from exc


def _split_quote(symbol: str) -> tuple[str, str]:
    for quote in _QUOTE_SUFFIXES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    return symbol, "USDT"


async def _get_json(http: aiohttp.ClientSession, url: str, params: Optional[dict] = None):
    """Returns (status, body). Never raises - a network failure just looks
    like 'no useful answer', which every provider below already treats the
    same as 'this exchange doesn't have it' - the caller tries the next one
    either way."""
    try:
        async with http.get(url, params=params) as resp:
            try:
                body = await resp.json()
            except Exception:  # noqa: BLE001 - not JSON, or empty body
                body = None
            return resp.status, body
    except aiohttp.ClientError as exc:
        logger.warning("Price provider request failed (%s): %s", url, exc)
        return None, None


async def _price_binance_futures(http: aiohttp.ClientSession, symbol: str) -> Optional[Decimal]:
    status, body = await _get_json(http, _FUTURES_TICKER_URL, {"symbol": symbol})
    if status == 200 and isinstance(body, dict) and "price" in body:
        return _to_decimal(body["price"])
    logger.info("binance_futures miss for %s: status=%s body=%s", symbol, status, str(body)[:200])
    return None


async def _price_binance_spot(http: aiohttp.ClientSession, symbol: str) -> Optional[Decimal]:
    status, body = await _get_json(http, _SPOT_TICKER_URL, {"symbol": symbol})
    if status == 200 and isinstance(body, dict) and "price" in body:
        return _to_decimal(body["price"])
    logger.info("binance_spot miss for %s: status=%s body=%s", symbol, status, str(body)[:200])
    return None


async def _price_bybit(http: aiohttp.ClientSession, symbol: str) -> Optional[Decimal]:
    status, body = await _get_json(http, _BYBIT_TICKER_URL, {"category": "linear", "symbol": symbol})
    if status == 200 and isinstance(body, dict) and body.get("retCode") == 0:
        items = ((body.get("result") or {}).get("list")) or []
        if items and items[0].get("lastPrice"):
            return _to_decimal(items[0]["lastPrice"])
    logger.info("bybit miss for %s: status=%s body=%s", symbol, status, str(body)[:200])
    return None


async def _price_mexc(http: aiohttp.ClientSession, symbol: str) -> Optional[Decimal]:
    base, quote = _split_quote(symbol)
    status, body = await _get_json(http, _MEXC_TICKER_URL, {"symbol": f"{base}_{quote}"})
    if status == 200 and isinstance(body, dict) and body.get("success"):
        data = body.get("data")
        if isinstance(data, list):
            data = data[0] if data else None
        if isinstance(data, dict):
            price = data.get("lastPrice") or data.get("fairPrice")
            if price is not None:
                return _to_decimal(price)
    logger.info("mexc miss for %s: status=%s body=%s", symbol, status, str(body)[:200])
    return None


# Futures first - this is a crypto FUTURES trading journal, and several
# newer tokens (e.g. VVV) launch as a Binance futures perpetual with no
# spot listing at all, so a spot-only lookup would wrongly call them
# "not found". Each remaining exchange is a genuine fallback, not a
# duplicate - different exchanges list different coins.
_PROVIDERS = [_price_binance_futures, _price_binance_spot, _price_bybit, _price_mexc]


async def get_price(symbol: str) -> Decimal:
    """Fetch a single symbol's current price, trying each exchange in turn.
    Used to validate a coin when creating an alert."""
    symbol = symbol.strip().upper()
    errors: list[str] = []
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        for provider in _PROVIDERS:
            try:
                price = await provider(http, symbol)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Price provider %s crashed for %s", provider.__name__, symbol)
                errors.append(f"{provider.__name__}: {exc}")
                continue
            if price is not None:
                return price
    logger.error("All price providers failed for %s: %s", symbol, "; ".join(errors))
    raise PriceLookupError(f"{symbol} hech bir exchange'da (Binance/Bybit/MEXC) topilmadi")


async def get_price_safe(symbol: str) -> Optional[Decimal]:
    """Same as get_price, but returns None instead of raising - for the
    background alert checker, where one bad symbol must never stop the
    whole batch."""
    try:
        return await get_price(symbol)
    except PriceLookupError:
        return None


async def get_all_prices() -> dict[str, Decimal]:
    """
    Fetch every Binance spot symbol's price in one request - used by the
    alert-checking background job so most active alerts cost one shared
    HTTP call, not one each. Symbols this doesn't cover (futures-only
    listings) are filled in individually by the caller via get_price_safe.
    """
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as http:
        async with http.get(_SPOT_TICKER_URL) as resp:
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


async def get_klines(symbol: str, interval: str = "15m", limit: int = 96) -> list[dict]:
    """
    Recent OHLC candles for the Mini App's candlestick chart -
    [{t, o, h, l, c}, ...], oldest first.
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
            out.append({
                "t": int(row[6]),
                "o": str(Decimal(row[1])),
                "h": str(Decimal(row[2])),
                "l": str(Decimal(row[3])),
                "c": str(Decimal(row[4])),
            })
        except (IndexError, InvalidOperation):
            continue
    return out
