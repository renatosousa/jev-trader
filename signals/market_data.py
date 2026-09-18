import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

DEFAULT_BASE_PRICES = {
    "EURUSD": 1.10,
    "GBPUSD": 1.27,
    "USDJPY": 149.0,
    "USDCHF": 0.88,
    "XAUUSD": 2000.0,
    "XAGUSD": 24.0,
    "USOIL": 70.0,
    "UKOIL": 74.0,
    "US10Y": 4.2,
    "BTCUSD": 60000.0,
    "ETHUSD": 3200.0,
}


@dataclass(frozen=True)
class Bar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, timeframe_minutes: int, count: int) -> list[Bar]:
        raise NotImplementedError

    @abstractmethod
    def get_last_price(self, symbol: str) -> float:
        raise NotImplementedError


class MockMarketDataProvider(MarketDataProvider):
    """Gera barras sintéticas determinísticas (random walk) para testes sem MT5."""

    def __init__(self, base_prices: dict | None = None, seed: int = 42):
        self.base_prices = base_prices or DEFAULT_BASE_PRICES
        self._seed = seed

    def get_bars(self, symbol: str, timeframe_minutes: int, count: int) -> list[Bar]:
        base_price = self.base_prices.get(symbol, 100.0)
        rng = random.Random(f"{self._seed}:{symbol}:{timeframe_minutes}")
        step_seconds = timeframe_minutes * 60
        now = time.time()

        price = base_price
        bars: list[Bar] = []
        for i in range(count):
            bars_from_now = count - 1 - i
            price += rng.gauss(0, base_price * 0.0015)
            intrabar_range = abs(rng.gauss(0, base_price * 0.001))
            bars.append(
                Bar(
                    timestamp=now - bars_from_now * step_seconds,
                    open=price,
                    high=price + intrabar_range,
                    low=price - intrabar_range,
                    close=price,
                    volume=abs(rng.gauss(1000, 300)),
                )
            )
        return bars

    def get_last_price(self, symbol: str) -> float:
        bars = self.get_bars(symbol, 60, 1)
        return bars[-1].close


class MT5MarketDataProvider(MarketDataProvider):
    """Assume que o terminal MT5 já está rodando e logado externamente pelo usuário."""

    def __init__(self):
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise RuntimeError(
                "Pacote MetaTrader5 não instalado. Instale com `pip install MetaTrader5` "
                "(requer Windows ou Wine com o terminal MT5 rodando)."
            ) from exc

        if not mt5.initialize():
            raise RuntimeError(
                f"mt5.initialize() falhou: {mt5.last_error()}. "
                "Confirme que o terminal MT5 está aberto e logado."
            )

    def get_bars(self, symbol: str, timeframe_minutes: int, count: int) -> list[Bar]:
        import MetaTrader5 as mt5

        timeframe = _mt5_timeframe(mt5, timeframe_minutes)
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None:
            raise RuntimeError(f"copy_rates_from_pos falhou para {symbol}: {mt5.last_error()}")

        return [
            Bar(
                timestamp=float(rate["time"]),
                open=float(rate["open"]),
                high=float(rate["high"]),
                low=float(rate["low"]),
                close=float(rate["close"]),
                volume=float(rate["tick_volume"]),
            )
            for rate in rates
        ]

    def get_last_price(self, symbol: str) -> float:
        import MetaTrader5 as mt5

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"symbol_info_tick falhou para {symbol}: {mt5.last_error()}")
        return float(tick.last or tick.bid)


def _mt5_timeframe(mt5, timeframe_minutes: int):
    known = {
        1: mt5.TIMEFRAME_M1,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        30: mt5.TIMEFRAME_M30,
        60: mt5.TIMEFRAME_H1,
        240: mt5.TIMEFRAME_H4,
        1440: mt5.TIMEFRAME_D1,
    }
    if timeframe_minutes not in known:
        raise ValueError(f"timeframe_minutes não suportado: {timeframe_minutes}")
    return known[timeframe_minutes]
