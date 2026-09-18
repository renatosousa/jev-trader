import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, send_from_directory

from signals.instruments import DEFAULT_BASKET
from signals.market_data import MockMarketDataProvider, MT5MarketDataProvider
from signals.signal_engine import generate_basket_signals, summarize_basket

PROVIDER_MODE = os.environ.get("SIGNAL_PROVIDER", "mock")
REFRESH_SECONDS = int(os.environ.get("DASHBOARD_REFRESH_SECONDS", "300"))
TIMEFRAME_MINUTES = int(os.environ.get("SIGNAL_TIMEFRAME_MINUTES", "60"))

MOCK_SYMBOLS = [instrument.symbol for instrument in DEFAULT_BASKET]
MT5_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "XAUUSD", "XAGUSD"]

app = Flask(__name__, static_folder="static", static_url_path="")

_state_lock = threading.Lock()
_state = {
    "signals": [],
    "summary": {"comprar": [], "vender": [], "manter": []},
    "updated_at": None,
    "provider": PROVIDER_MODE,
    "error": None,
    "updating": False,
}


def _resolve_symbols(default: list[str]) -> list[str]:
    override = os.environ.get("SIGNAL_SYMBOLS")
    if override:
        return [s.strip() for s in override.split(",") if s.strip()]
    return default


def _build_provider():
    if PROVIDER_MODE == "mt5":
        return MT5MarketDataProvider(), _resolve_symbols(MT5_SYMBOLS)
    return MockMarketDataProvider(seed=int(time.time())), _resolve_symbols(MOCK_SYMBOLS)


def _refresh_loop():
    while True:
        with _state_lock:
            _state["updating"] = True
        try:
            provider, symbols = _build_provider()
            signals = generate_basket_signals(symbols, provider, timeframe_minutes=TIMEFRAME_MINUTES)
            summary = summarize_basket(signals)
            with _state_lock:
                _state["signals"] = [_signal_to_dict(s) for s in signals]
                _state["summary"] = summary
                _state["updated_at"] = time.time()
                _state["error"] = None
        except Exception as exc:  # noqa: BLE001 - reporta qualquer falha no dashboard em vez de derrubar o loop
            with _state_lock:
                _state["error"] = str(exc)
        finally:
            with _state_lock:
                _state["updating"] = False
        time.sleep(REFRESH_SECONDS)


def _signal_to_dict(signal) -> dict:
    state = signal.raw_state.to_state_dict()
    return {
        "symbol": signal.symbol,
        "action": signal.action,
        "strength": signal.strength,
        "conviction": signal.conviction,
        "raw_bias_score": signal.raw_bias_score,
        "summary": state["summary"],
        "rsi": state["rsi"],
        "volatility_regime": state["volatility_regime"],
    }


@app.get("/api/signals")
def api_signals():
    with _state_lock:
        return jsonify(dict(_state))


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    threading.Thread(target=_refresh_loop, daemon=True).start()
    app.run(host="127.0.0.1", port=int(os.environ.get("DASHBOARD_PORT", "5050")), debug=False)
