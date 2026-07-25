from historical.multi_timeframe_research import (
    CONFIG,
    TIMEFRAMES,
    fetch_max_950,
    calculate_context,
)

from historical.indicator_combination_research import (
    prepare_candles,
    build_indicator_states,
    get_combinations,
    cross_timeframe_combinations,
)


def classify_live_regime(context_5m, context_15m):
    trend5 = context_5m.get("trend", "NO_DATA")
    trend15 = context_15m.get("trend", "NO_DATA")

    mom5 = context_5m.get("momentum", "NO_DATA")
    mom15 = context_15m.get("momentum", "NO_DATA")

    if trend5 == "BULLISH" and trend15 == "BULLISH":
        return "BULL_TREND"

    if trend5 == "BEARISH" and trend15 == "BEARISH":
        return "BEAR_TREND"

    if trend5 == "RANGE" and trend15 == "RANGE":
        return "SIDEWAYS"

    if (
        trend5 == "BULLISH"
        or trend15 == "BULLISH"
        or mom5 == "BULLISH"
        or mom15 == "BULLISH"
    ):
        return "BULL_MIXED"

    if (
        trend5 == "BEARISH"
        or trend15 == "BEARISH"
        or mom5 == "BEARISH"
        or mom15 == "BEARISH"
    ):
        return "BEAR_MIXED"

    return "SIDEWAYS"


def choose_live_combination(state_5m, state_15m):
    cross = cross_timeframe_combinations(
        state_5m,
        state_15m,
    )

    for name, direction in cross.items():
        if direction in ("BULLISH", "BEARISH"):
            return name, direction

    combinations_5m = get_combinations(state_5m)

    for name, direction in combinations_5m.items():
        if direction in ("BULLISH", "BEARISH"):
            return name, direction

    return "NO_VALID_COMBINATION", "NEUTRAL"


def build_live_spot_context(api, index_name):
    if index_name not in CONFIG:
        raise ValueError(
            f"Unsupported index: {index_name}"
        )

    cfg = CONFIG[index_name]

    rows_5m = fetch_max_950(
        api,
        cfg["segment"],
        cfg["token"],
        TIMEFRAMES["5M"]["api_interval"],
        TIMEFRAMES["5M"]["chunk_days"],
    )

    rows_15m = fetch_max_950(
        api,
        cfg["segment"],
        cfg["token"],
        TIMEFRAMES["15M"]["api_interval"],
        TIMEFRAMES["15M"]["chunk_days"],
    )

    if not rows_5m or not rows_15m:
        return {
            "valid": False,
            "reason": "NO_CANDLE_DATA",
        }

    candles_5m = prepare_candles(rows_5m)
    candles_15m = prepare_candles(rows_15m)

    if len(candles_5m) < 50 or len(candles_15m) < 50:
        return {
            "valid": False,
            "reason": "INSUFFICIENT_CANDLES",
        }

    states_5m = build_indicator_states(candles_5m)
    states_15m = build_indicator_states(candles_15m)

    state_5m = states_5m[-1]
    state_15m = states_15m[-1]

    context_5m = calculate_context(rows_5m)
    context_15m = calculate_context(rows_15m)

    regime = classify_live_regime(
        context_5m,
        context_15m,
    )

    combination, direction = choose_live_combination(
        state_5m,
        state_15m,
    )

    return {
        "valid": direction in ("BULLISH", "BEARISH"),
        "index": index_name,
        "regime": regime,
        "direction": direction,
        "combination": combination,
        "context_5m": context_5m,
        "context_15m": context_15m,
        "state_5m": state_5m,
        "state_15m": state_15m,
        "spot_close": candles_5m[-1]["close"],
    }
