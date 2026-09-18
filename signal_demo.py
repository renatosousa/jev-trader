from signals.instruments import DEFAULT_BASKET
from signals.market_data import MockMarketDataProvider
from signals.signal_engine import generate_basket_signals, summarize_basket

if __name__ == "__main__":
    provider = MockMarketDataProvider(seed=7)
    symbols = [instrument.symbol for instrument in DEFAULT_BASKET][:3]

    signals = generate_basket_signals(symbols, provider, timeframe_minutes=60)

    for s in signals:
        print(
            f"[{s.symbol:8s}] {s.action:8s} | strength={s.strength:.2f} "
            f"conviction={s.conviction:.2f} bias_score={s.raw_bias_score:.2f} | "
            f"{s.raw_state.to_state_dict()['summary']}"
        )

    print("\nResumo da cesta:")
    print(summarize_basket(signals))
