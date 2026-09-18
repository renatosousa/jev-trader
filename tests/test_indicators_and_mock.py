import pytest

from signals.indicators import (
    atr,
    distance_to_ma_pct,
    moving_average,
    rsi,
    simple_return,
    volatility_regime,
)
from signals.market_data import Bar, MockMarketDataProvider


def _manual_bars():
    closes = [10, 11, 12, 11, 10, 9, 10]
    return [
        Bar(timestamp=float(i), open=c, high=c, low=c, close=float(c), volume=1.0)
        for i, c in enumerate(closes)
    ]


def test_simple_return():
    bars = _manual_bars()
    assert simple_return(bars, 1) == pytest.approx(11.111111111111112)
    assert simple_return(bars, 2) == pytest.approx(0.0)
    assert simple_return(bars, 3) == pytest.approx(-9.090909090909092)
    assert simple_return(bars, 10) == 0.0


def test_moving_average_and_distance():
    bars = _manual_bars()
    assert moving_average(bars, 3) == pytest.approx(9.666666666666666)
    assert distance_to_ma_pct(bars, 3) == pytest.approx(3.448275862068966)
    assert moving_average(bars, 7) == pytest.approx(73 / 7)
    assert moving_average(bars, 8) == 0.0
    assert distance_to_ma_pct(bars, 8) == 0.0


def test_rsi_range():
    provider = MockMarketDataProvider(seed=123)
    bars = provider.get_bars("EURUSD", 60, 50)
    result = rsi(bars, 14)
    assert 0.0 <= result <= 100.0


def test_atr_non_negative():
    provider = MockMarketDataProvider(seed=123)
    bars = provider.get_bars("EURUSD", 60, 50)
    assert atr(bars, 14) >= 0.0


def test_mock_determinism():
    provider1 = MockMarketDataProvider(seed=1)
    provider2 = MockMarketDataProvider(seed=1)
    bars1 = provider1.get_bars("EURUSD", 60, 50)
    bars2 = provider2.get_bars("EURUSD", 60, 50)
    assert [b.close for b in bars1] == [b.close for b in bars2]


def test_get_bars_count_and_chronological_order():
    provider = MockMarketDataProvider(seed=1)
    bars = provider.get_bars("EURUSD", 60, 50)
    assert len(bars) == 50
    assert bars[-1].timestamp > bars[0].timestamp


def test_volatility_regime_valid_output():
    provider = MockMarketDataProvider(seed=1)
    bars = provider.get_bars("EURUSD", 60, 50)
    assert volatility_regime(bars) in ("baixa", "normal", "alta")
    assert volatility_regime([]) in ("baixa", "normal", "alta")
    assert volatility_regime([Bar(0.0, 1.0, 1.0, 1.0, 1.0, 1.0)]) in ("baixa", "normal", "alta")


def test_fallbacks_with_insufficient_data():
    bars = [Bar(timestamp=0.0, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0)]
    assert simple_return(bars, 2) == 0.0
    assert rsi(bars, 14) == 50.0
    assert moving_average(bars, 2) == 0.0
    assert distance_to_ma_pct(bars, 2) == 0.0
    assert atr(bars, 14) == 0.0
    assert volatility_regime(bars, 14, 100) in ("baixa", "normal", "alta")
