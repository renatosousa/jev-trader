from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AssetClass(Enum):
    FX = "FX"
    METAL = "METAL"
    ENERGY = "ENERGY"
    RATES = "RATES"
    CRYPTO = "CRYPTO"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    display_name: str
    asset_class: AssetClass
    pip_size: float


DEFAULT_BASKET: list[Instrument] = [
    Instrument("EURUSD", "Euro/Dólar", AssetClass.FX, 0.0001),
    Instrument("GBPUSD", "Libra/Dólar", AssetClass.FX, 0.0001),
    Instrument("USDJPY", "Dólar/Yen", AssetClass.FX, 0.01),
    Instrument("USDCHF", "Dólar/Franco", AssetClass.FX, 0.0001),
    Instrument("XAUUSD", "Ouro", AssetClass.METAL, 0.1),
    Instrument("XAGUSD", "Prata", AssetClass.METAL, 0.01),
    Instrument("USOIL", "WTI", AssetClass.ENERGY, 0.01),
    Instrument("UKOIL", "Brent", AssetClass.ENERGY, 0.01),
    Instrument("US10Y", "Treasury Yield 10 anos (proxy)", AssetClass.RATES, 0.001),
    Instrument("BTCUSD", "Bitcoin", AssetClass.CRYPTO, 1.0),
    Instrument("ETHUSD", "Ethereum", AssetClass.CRYPTO, 0.1),
]


def get_instrument(symbol: str) -> Optional[Instrument]:
    for instrument in DEFAULT_BASKET:
        if instrument.symbol == symbol:
            return instrument
    return None
