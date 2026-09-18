import statistics

from .market_data import Bar


def simple_return(bars: list[Bar], lookback: int) -> float:
    if len(bars) < lookback + 1:
        return 0.0
    return (bars[-1].close - bars[-lookback - 1].close) / bars[-lookback - 1].close * 100


def rsi(bars: list[Bar], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 50.0

    gains = []
    losses = []
    for i in range(1, len(bars)):
        change = bars[i].close - bars[i - 1].close
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    avg_gain = statistics.mean(gains[-period:])
    avg_loss = statistics.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def moving_average(bars: list[Bar], period: int) -> float:
    if len(bars) < period or period <= 0:
        return 0.0
    return statistics.mean(bar.close for bar in bars[-period:])


def distance_to_ma_pct(bars: list[Bar], period: int) -> float:
    ma = moving_average(bars, period)
    if ma == 0 or not bars:
        return 0.0
    return (bars[-1].close - ma) / ma * 100


def atr(bars: list[Bar], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    true_ranges = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        true_ranges.append(tr)
    if not true_ranges:
        return 0.0
    return statistics.mean(true_ranges[-period:])


def volatility_regime(bars: list[Bar], atr_period: int = 14, lookback_periods: int = 100) -> str:
    if len(bars) < atr_period + 10:
        return "normal"

    current_atr = atr(bars, atr_period)
    window = bars[-lookback_periods:] if len(bars) > lookback_periods else bars
    historical_atrs = []
    for i in range(atr_period + 1, len(window)):
        historical_atrs.append(atr(window[: i + 1], atr_period))

    if len(historical_atrs) < 4:
        return "normal"

    q1, _, q3 = statistics.quantiles(historical_atrs, n=4)
    if current_atr < q1:
        return "baixa"
    if current_atr > q3:
        return "alta"
    return "normal"
