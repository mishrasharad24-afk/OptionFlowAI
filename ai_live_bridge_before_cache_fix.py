from historical.multi_timeframe_research import (
    CONFIG,
    TIMEFRAMES,
    fetch_max_950,
    calculate_context,
)

from historical.market_regime_combination_research import detect_local_regime

from historical.indicator_combination_research import (
    prepare_candles,
    build_indicator_states,
    get_combinations,
    cross_timeframe_combinations,
)

from historical.price_action_regime_research import (
    build_price_action_states,
    get_price_action_combinations,
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


def choose_live_combination(
    state_5m,
    state_15m,
    pa_state_5m,
):
    """
    Build live combinations using the same indicator
    and price-action naming used by historical research.
    """

    # Prefer 5M + 15M indicator agreement.
    cross = cross_timeframe_combinations(
        state_5m,
        state_15m,
    )

    cross_pa = get_price_action_combinations(
        cross,
        pa_state_5m,
    )

    for name, direction in cross_pa.items():
        if direction in ("BULLISH", "BEARISH"):
            return name, direction

    # Fallback to 5M indicator + price action.
    combinations_5m = get_combinations(
        state_5m
    )

    combinations_5m_pa = get_price_action_combinations(
        combinations_5m,
        pa_state_5m,
    )

    for name, direction in combinations_5m_pa.items():
        if direction in ("BULLISH", "BEARISH"):
            return name, direction

    return "NO_VALID_COMBINATION", "NEUTRAL"

def build_live_spot_context(
    api,
    index_name,
    live_5m=None,
    live_15m=None,
):
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

    # Merge current live candles with historical data.
    # Historical API may not contain today's intraday candles.
    if live_5m:
        rows_5m = merge_live_candle(
            rows_5m,
            live_5m,
        )

    if live_15m:
        rows_15m = merge_live_candle(
            rows_15m,
            live_15m,
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

    pa_states_5m = build_price_action_states(
        candles_5m
    )
    pa_state_5m = pa_states_5m[-1]

    context_5m = calculate_context(rows_5m)
    context_15m = calculate_context(rows_15m)

    regime = detect_local_regime(
        candles_5m,
        len(candles_5m) - 1,
        lookback=12,
    )

    combination, direction = choose_live_combination(
        state_5m,
        state_15m,
        pa_state_5m,
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
        "pa_state_5m": pa_state_5m,
        "spot_close": candles_5m[-1]["close"],
    }


# ============================================================
# LIVE CANDLE MERGE SUPPORT
# ============================================================

def live_candle_to_row(candle):
    """
    Convert LiveCandleBuilder candle dict into the same
    row format used by historical research:
    [time, open, high, low, close, volume]
    """

    if not candle:
        return None

    return [
        candle["timestamp"],
        candle["open"],
        candle["high"],
        candle["low"],
        candle["close"],
        candle.get("volume", 0),
    ]


def merge_live_candle(rows, live_candle):
    """
    Merge one live candle with historical rows.

    If timestamp already exists, replace that candle.
    Otherwise append it.

    Returns rows sorted by timestamp.
    """

    if not live_candle:
        return list(rows)

    live_row = live_candle_to_row(
        live_candle
    )

    merged = {
        row[0]: row
        for row in rows
        if row
    }

    merged[live_row[0]] = live_row

    return sorted(
        merged.values(),
        key=lambda x: x[0],
    )
