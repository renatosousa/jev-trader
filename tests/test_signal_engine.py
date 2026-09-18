import signals.signal_engine as signal_engine
from signals.market_data import MockMarketDataProvider
from signals.signal_engine import Signal, TechnicalState, generate_signal, summarize_basket


def _fake_bridge(bias_score, act_now_probability):
    def _call(state, questions, base_url=signal_engine.JEV_BRIDGE_URL):
        return {
            "bias": {"type": "score", "score": bias_score, "probabilities": {}},
            "act_now": {"type": "boolean", "probability": act_now_probability},
        }

    return _call


def test_generate_signal_maps_high_bias_to_buy(monkeypatch):
    monkeypatch.setattr(signal_engine, "call_jev_bridge", _fake_bridge(3.8, 0.9))
    provider = MockMarketDataProvider(seed=1)

    signal = generate_signal("EURUSD", provider, timeframe_minutes=60)

    assert signal.action == "comprar"
    assert signal.conviction == 0.9
    assert 0.0 <= signal.strength <= 1.0
    assert isinstance(signal.raw_state, TechnicalState)


def test_generate_signal_maps_low_bias_to_sell(monkeypatch):
    monkeypatch.setattr(signal_engine, "call_jev_bridge", _fake_bridge(0.5, 0.7))
    provider = MockMarketDataProvider(seed=1)

    signal = generate_signal("XAUUSD", provider, timeframe_minutes=60)

    assert signal.action == "vender"


def test_generate_signal_maps_neutral_bias_to_hold(monkeypatch):
    monkeypatch.setattr(signal_engine, "call_jev_bridge", _fake_bridge(2.0, 0.3))
    provider = MockMarketDataProvider(seed=1)

    signal = generate_signal("BTCUSD", provider, timeframe_minutes=60)

    assert signal.action == "manter"


def test_summarize_basket_respects_conviction_floor():
    state = TechnicalState("X", 60, 0.0, 0.0, 50.0, 0.0, "normal")
    signals = [
        Signal("EURUSD", "comprar", 0.8, 0.9, 3.8, state),
        Signal("GBPUSD", "vender", 0.7, 0.2, 0.6, state),
        Signal("USDJPY", "comprar", 0.1, 1.0, 2.6, state),
    ]

    grouped = summarize_basket(signals, conviction_floor=0.5)

    assert grouped == {
        "comprar": ["EURUSD", "USDJPY"],
        "vender": [],
        "manter": ["GBPUSD"],
    }
