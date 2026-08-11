"""Stock price data via yfinance (no API key required) - the only external client this
module owns.

Two failure modes are deliberately swallowed rather than raised: an invalid ticker or a
transient network/yfinance-library issue both just mean "no price data available right
now," which the frontend already handles as an empty chart / null price rather than an
error page - a 500 from a flaky third-party data source would be a worse user experience
than a temporarily-empty chart. Current-price lookups are cached in-process for
CACHE_TTL_MINUTES to avoid re-hitting yfinance on every page load/re-render; historical
data is not cached here since React Query's own `staleTime` (see
frontend/src/features/investments/hooks/useInvestments.ts) already covers that at the
call-site level.
"""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import yfinance as yf

CACHE_TTL_MINUTES = 15
_CENTS = Decimal("0.01")

VALID_HISTORY_PERIODS = {"1d", "1mo", "3mo", "1y", "5y"}
DEFAULT_HISTORY_PERIOD = "3mo"

# In-process cache: ticker -> (price, fetched_at). Module-level and unbounded - acceptable
# for V1 given the app only ever fetches a handful of tickers per user session (the
# default S&P 500 index plus whatever a user searches/holds), not a large universe.
_price_cache: dict[str, tuple[Decimal, datetime]] = {}


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(_CENTS)
    except (InvalidOperation, ValueError):
        return None


def get_current_price(ticker: str) -> Decimal | None:
    """Current market price for `ticker`, or None if the ticker is invalid or the fetch
    fails. Serves a cached value (see CACHE_TTL_MINUTES) when available and fresh."""
    cache_key = ticker.upper().strip()
    if not cache_key:
        return None

    now = datetime.utcnow()
    cached = _price_cache.get(cache_key)
    if cached is not None:
        price, fetched_at = cached
        if now - fetched_at < timedelta(minutes=CACHE_TTL_MINUTES):
            return price

    try:
        info = yf.Ticker(cache_key).fast_info
        raw_price = info.get("lastPrice") if hasattr(info, "get") else getattr(info, "last_price", None)
    except Exception:
        return None

    price = _to_decimal(raw_price)
    if price is not None:
        _price_cache[cache_key] = (price, now)
    return price


def get_price_history(ticker: str, period: str = DEFAULT_HISTORY_PERIOD) -> list[dict]:
    """Historical OHLCV data for `ticker` over `period` (one of VALID_HISTORY_PERIODS,
    falling back to DEFAULT_HISTORY_PERIOD for an unrecognized value). Returns an empty
    list - never raises - on an invalid ticker or a fetch failure, so a chart with no data
    is the worst case, not a 500."""
    if period not in VALID_HISTORY_PERIODS:
        period = DEFAULT_HISTORY_PERIOD

    cache_key = ticker.upper().strip()
    if not cache_key:
        return []

    try:
        history = yf.Ticker(cache_key).history(period=period)
    except Exception:
        return []

    if history is None or history.empty:
        return []

    points: list[dict] = []
    for index, row in history.iterrows():
        open_price = _to_decimal(row.get("Open"))
        high_price = _to_decimal(row.get("High"))
        low_price = _to_decimal(row.get("Low"))
        close_price = _to_decimal(row.get("Close"))
        if None in (open_price, high_price, low_price, close_price):
            continue
        points.append(
            {
                "date": index.date() if hasattr(index, "date") else index,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": int(row.get("Volume") or 0),
            }
        )
    return points


def validate_ticker(ticker: str) -> bool:
    """True if `ticker` resolves to a real, currently-priced instrument."""
    return get_current_price(ticker) is not None
