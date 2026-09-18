import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .indicators import distance_to_ma_pct, rsi, simple_return, volatility_regime
from .market_data import MarketDataProvider

JEV_BRIDGE_URL = "http://127.0.0.1:8787/evaluate"
BIAS_LEVELS = ["Forte venda", "Venda", "Neutro", "Compra", "Forte compra"]

# Deve ser maior que JEV_MIN_INTERVAL_MS do bridge (bridge/server.mjs) + a
# latência real da chamada ao Jev: uma requisição pode ficar na fila do
# bridge esperando o intervalo mínimo entre chamadas antes de ser processada.
JEV_REQUEST_TIMEOUT_SECONDS = 120


def call_jev_bridge(
    state: dict,
    questions: dict,
    base_url: str = JEV_BRIDGE_URL,
    timeout: float = JEV_REQUEST_TIMEOUT_SECONDS,
) -> dict:
    body = json.dumps({"state": state, "questions": questions}).encode("utf-8")
    req = urllib.request.Request(
        base_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"jev bridge retornou HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"não foi possível conectar ao jev bridge em {base_url}: {exc.reason}") from exc

    if "answers" not in payload:
        raise RuntimeError(f"resposta inesperada do jev bridge: {payload}")
    return payload["answers"]


@dataclass(frozen=True)
class TechnicalState:
    symbol: str
    timeframe_minutes: int
    momentum_pct: float
    trend_pct: float
    rsi: float
    distance_to_ma_pct: float
    volatility_regime: str

    def to_state_dict(self) -> dict:
        rsi_zone = "sobrevenda" if self.rsi < 30 else "sobrecompra" if self.rsi > 70 else "zona neutra"
        summary = (
            f"RSI em {self.rsi:.0f} ({rsi_zone}), "
            f"preço {self.distance_to_ma_pct:+.2f}% em relação à média de 50 períodos, "
            f"momentum de curto prazo {self.momentum_pct:+.2f}% nas últimas 20 velas, "
            f"variação de {self.trend_pct:+.2f}% no período mais longo analisado, "
            f"volatilidade {self.volatility_regime}."
        )
        return {
            "symbol": self.symbol,
            "timeframe_minutes": self.timeframe_minutes,
            "momentum_pct": round(self.momentum_pct, 4),
            "trend_pct": round(self.trend_pct, 4),
            "rsi": round(self.rsi, 2),
            "distance_to_ma_pct": round(self.distance_to_ma_pct, 4),
            "volatility_regime": self.volatility_regime,
            "summary": summary,
        }


def build_technical_state(symbol: str, provider: MarketDataProvider, timeframe_minutes: int = 60) -> TechnicalState:
    bars = provider.get_bars(symbol, timeframe_minutes, 210)
    return TechnicalState(
        symbol=symbol,
        timeframe_minutes=timeframe_minutes,
        momentum_pct=simple_return(bars, 20),
        trend_pct=simple_return(bars, 100),
        rsi=rsi(bars, 14),
        distance_to_ma_pct=distance_to_ma_pct(bars, 50),
        volatility_regime=volatility_regime(bars),
    )


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: str
    strength: float
    conviction: float
    raw_bias_score: float
    raw_state: TechnicalState


def _max_probability(probabilities: dict | None) -> float:
    if not probabilities:
        return 0.0
    return max(probabilities.values())


def generate_signal(symbol: str, provider: MarketDataProvider, timeframe_minutes: int = 60) -> Signal:
    state = build_technical_state(symbol, provider, timeframe_minutes)

    answers = call_jev_bridge(
        state=state.to_state_dict(),
        questions={
            "bias": {
                "type": "score",
                "instructions": (
                    "Dado o estado técnico descrito em `summary` para `symbol`, qual o viés "
                    "direcional recomendado?"
                ),
                "criteria": BIAS_LEVELS,
            },
            "act_now": {
                "type": "boolean",
                "instructions": (
                    "O setup descrito em `summary` é forte o suficiente para agir agora, em vez "
                    "de esperar confirmação adicional?"
                ),
            },
        },
    )

    bias = answers["bias"]
    act_now = answers["act_now"]

    bias_score = bias.get("score", 2.0)
    top_level = len(BIAS_LEVELS) - 1
    strength = abs((bias_score / top_level) * 2 - 1)

    if bias_score < 1.5:
        action = "vender"
    elif bias_score > 2.5:
        action = "comprar"
    else:
        action = "manter"

    conviction = act_now.get("probability")
    if conviction is None:
        conviction = _max_probability(act_now.get("probabilities"))

    return Signal(
        symbol=symbol,
        action=action,
        strength=strength,
        conviction=conviction,
        raw_bias_score=bias_score,
        raw_state=state,
    )


def generate_basket_signals(
    symbols: list[str], provider: MarketDataProvider, timeframe_minutes: int = 60
) -> list[Signal]:
    return [generate_signal(symbol, provider, timeframe_minutes) for symbol in symbols]


def summarize_basket(signals: list[Signal], conviction_floor: float = 0.5) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {"comprar": [], "vender": [], "manter": []}
    for signal in signals:
        if signal.conviction >= conviction_floor and signal.action in ("comprar", "vender"):
            grouped[signal.action].append(signal.symbol)
        else:
            grouped["manter"].append(signal.symbol)
    return grouped
