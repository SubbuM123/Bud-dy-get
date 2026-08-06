"""Unit tests for services/stock_price.py's yfinance wrapper. Mocks yf.Ticker entirely -
no real network calls, matching how tests/test_receipts.py stubs out storage.py's S3 calls
rather than hitting real external services. Runs under plain pytest, no client/db fixture.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd

from app.services import stock_price


class _FakeFastInfo(dict):
    """Mimics yfinance's dict-like fast_info object."""


class _FakeTicker:
    def __init__(self, price=None, history_df=None, raise_on_history=False):
        self.fast_info = _FakeFastInfo({"lastPrice": price} if price is not None else {})
        self._history_df = history_df if history_df is not None else pd.DataFrame()
        self._raise_on_history = raise_on_history

    def history(self, period="3mo"):
        if self._raise_on_history:
            raise RuntimeError("simulated network error")
        return self._history_df


def _sample_history_df():
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [104.0, 105.0, 106.0],
            "Volume": [1000, 1100, 1200],
        },
        index=index,
    )


def setup_function():
    # Clear the module-level price cache between tests so results don't leak across cases.
    stock_price._price_cache.clear()


def test_get_current_price_returns_decimal(monkeypatch):
    monkeypatch.setattr(stock_price.yf, "Ticker", lambda ticker: _FakeTicker(price=123.45))

    assert stock_price.get_current_price("ACME") == Decimal("123.45")


def test_get_current_price_returns_none_on_missing_ticker(monkeypatch):
    monkeypatch.setattr(stock_price.yf, "Ticker", lambda ticker: _FakeTicker(price=None))

    assert stock_price.get_current_price("BOGUS") is None


def test_get_current_price_returns_none_on_exception(monkeypatch):
    def _raise(ticker):
        raise RuntimeError("simulated network error")

    monkeypatch.setattr(stock_price.yf, "Ticker", _raise)

    assert stock_price.get_current_price("ACME") is None


def test_get_current_price_is_cached_within_ttl(monkeypatch):
    call_count = {"n": 0}

    def _factory(ticker):
        call_count["n"] += 1
        return _FakeTicker(price=100.00)

    monkeypatch.setattr(stock_price.yf, "Ticker", _factory)

    first = stock_price.get_current_price("ACME")
    second = stock_price.get_current_price("ACME")

    assert first == second == Decimal("100.00")
    assert call_count["n"] == 1


def test_get_current_price_refetches_after_cache_expires(monkeypatch):
    call_count = {"n": 0}

    def _factory(ticker):
        call_count["n"] += 1
        return _FakeTicker(price=100.00)

    monkeypatch.setattr(stock_price.yf, "Ticker", _factory)
    stock_price.get_current_price("ACME")

    # Manually expire the cache entry rather than sleeping in a test.
    price, _ = stock_price._price_cache["ACME"]
    stock_price._price_cache["ACME"] = (price, datetime.utcnow() - timedelta(minutes=20))

    stock_price.get_current_price("ACME")

    assert call_count["n"] == 2


def test_get_price_history_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        stock_price.yf, "Ticker", lambda ticker: _FakeTicker(history_df=_sample_history_df())
    )

    points = stock_price.get_price_history("ACME", period="1mo")

    assert len(points) == 3
    assert points[0]["close"] == Decimal("104.00")
    assert points[0]["volume"] == 1000


def test_get_price_history_returns_empty_list_on_invalid_ticker(monkeypatch):
    monkeypatch.setattr(
        stock_price.yf, "Ticker", lambda ticker: _FakeTicker(history_df=pd.DataFrame())
    )

    assert stock_price.get_price_history("BOGUS") == []


def test_get_price_history_returns_empty_list_on_exception(monkeypatch):
    monkeypatch.setattr(
        stock_price.yf, "Ticker", lambda ticker: _FakeTicker(raise_on_history=True)
    )

    assert stock_price.get_price_history("ACME") == []


def test_get_price_history_falls_back_to_default_period_for_unrecognized_value(monkeypatch):
    seen_periods = []

    class _RecordingTicker(_FakeTicker):
        def history(self, period="3mo"):
            seen_periods.append(period)
            return super().history(period)

    monkeypatch.setattr(
        stock_price.yf, "Ticker", lambda ticker: _RecordingTicker(history_df=_sample_history_df())
    )

    stock_price.get_price_history("ACME", period="not-a-real-period")

    assert seen_periods == [stock_price.DEFAULT_HISTORY_PERIOD]


def test_validate_ticker_true_for_valid_ticker(monkeypatch):
    monkeypatch.setattr(stock_price.yf, "Ticker", lambda ticker: _FakeTicker(price=50.00))

    assert stock_price.validate_ticker("ACME") is True


def test_validate_ticker_false_for_invalid_ticker(monkeypatch):
    monkeypatch.setattr(stock_price.yf, "Ticker", lambda ticker: _FakeTicker(price=None))

    assert stock_price.validate_ticker("BOGUS") is False
