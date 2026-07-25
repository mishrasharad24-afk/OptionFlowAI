"""
SCALPER MODE RESEARCH - PHASE 1

Goal:
Detect early intraday directional moves on 5M candles.

This research file is independent from the live bot.
It reuses the existing 950-candle historical infrastructure.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from historical.multi_timeframe_research import (
    CONFIG,
    TIMEFRAMES,
    fetch_max_950,
    fetch_chunk,
)

from historical.indicator_combination_research import (
    prepare_candles,
    build_indicator_states,
    future_outcome,
)

from historical.price_action_regime_research import (
    build_price_action_states,
)


FORWARD_WINDOWS = [1, 2, 3, 5]


def create_stats():
    return {
        "total": 0,
        "correct": 0,
        "bullish": 0,
        "bearish": 0,
        "move_sum": 0.0,
    }


def update_stats(stats, signal, outcome):
    if signal not in ("BULLISH", "BEARISH"):
        return

    if not outcome:
        return

    actual = outcome["direction"]

    if actual == "FLAT":
        return

    stats["total"] += 1
    stats["move_sum"] += outcome["move_pct"]

    if signal == "BULLISH":
        stats["bullish"] += 1

    if signal == "BEARISH":
        stats["bearish"] += 1

    if signal == actual:
        stats["correct"] += 1




# ============================================================
# PHASE-2A CANDLE MICROSTRUCTURE FEATURES
# ============================================================

def _ohlc(candle):
    return (
        float(candle["open"]),
        float(candle["high"]),
        float(candle["low"]),
        float(candle["close"]),
    )


def compression_expansion_signal(candles, i, lookback=3):
    """
    Detect range compression followed by directional expansion.
    """

    if i < lookback:
        return None

    previous = candles[i-lookback:i]

    previous_ranges = [
        float(c["high"]) - float(c["low"])
        for c in previous
    ]

    avg_range = sum(previous_ranges) / len(previous_ranges)

    o, h, l, c = _ohlc(candles[i])
    current_range = h - l

    if avg_range <= 0 or current_range <= 0:
        return None

    # Expansion must be meaningfully larger
    if current_range < avg_range * 1.35:
        return None

    body = abs(c - o)
    body_ratio = body / current_range

    if body_ratio < 0.55:
        return None

    if c > o:
        return "BULLISH"

    if c < o:
        return "BEARISH"

    return None


def failed_break_signal(candles, i, lookback=3):
    """
    Detect failed breakout / failed breakdown.

    Price trades beyond recent structure
    but closes back inside it.
    """

    if i < lookback:
        return None

    previous = candles[i-lookback:i]

    previous_high = max(
        float(c["high"])
        for c in previous
    )

    previous_low = min(
        float(c["low"])
        for c in previous
    )

    o, h, l, c = _ohlc(candles[i])

    # Failed upside breakout -> bearish
    if h > previous_high and c < previous_high:
        return "BEARISH"

    # Failed downside breakdown -> bullish
    if l < previous_low and c > previous_low:
        return "BULLISH"

    return None


def high_low_progression_signal(candles, i):
    """
    Detect short-term lower-high or higher-low progression.
    """

    if i < 2:
        return None

    c0 = candles[i-2]
    c1 = candles[i-1]
    c2 = candles[i]

    h0 = float(c0["high"])
    h1 = float(c1["high"])
    h2 = float(c2["high"])

    l0 = float(c0["low"])
    l1 = float(c1["low"])
    l2 = float(c2["low"])

    # Three progressively lower highs
    if h2 < h1 < h0:
        return "BEARISH"

    # Three progressively higher lows
    if l2 > l1 > l0:
        return "BULLISH"

    return None


def close_location_signal(candle):
    """
    Detect where candle closes inside its total range.

    Top 25% = bullish pressure
    Bottom 25% = bearish pressure
    """

    o, h, l, c = _ohlc(candle)

    total_range = h - l

    if total_range <= 0:
        return None

    close_position = (
        (c - l) / total_range
    )

    if close_position >= 0.75:
        return "BULLISH"

    if close_position <= 0.25:
        return "BEARISH"

    return None


def micro_structure_break_signal(candles, i, lookback=2):
    """
    Faster structure break than the existing 5-candle swing break.
    """

    if i < lookback:
        return None

    previous = candles[i-lookback:i]

    previous_high = max(
        float(c["high"])
        for c in previous
    )

    previous_low = min(
        float(c["low"])
        for c in previous
    )

    current_close = float(
        candles[i]["close"]
    )

    if current_close > previous_high:
        return "BULLISH"

    if current_close < previous_low:
        return "BEARISH"

    return None


def build_microstructure_states(candles):
    """
    Build all Phase-2A feature states for every candle.
    """

    states = []

    for i in range(len(candles)):

        states.append({
            "COMPRESSION_EXPANSION":
                compression_expansion_signal(candles, i),

            "FAILED_BREAK":
                failed_break_signal(candles, i),

            "HIGH_LOW_PROGRESSION":
                high_low_progression_signal(candles, i),

            "CLOSE_LOCATION":
                close_location_signal(candles[i]),

            "MICRO_STRUCTURE_BREAK":
                micro_structure_break_signal(candles, i),
        })

    return states


def calculate_mfe_mae(
    candles,
    index,
    window,
    signal,
):
    """
    Calculate Maximum Favorable Excursion (MFE)
    and Maximum Adverse Excursion (MAE)
    after a scalper signal.
    """

    if signal not in ("BULLISH", "BEARISH"):
        return None

    if index >= len(candles):
        return None

    entry = float(
        candles[index]["close"]
    )

    if entry <= 0:
        return None

    end_index = min(
        index + window + 1,
        len(candles),
    )

    future = candles[
        index + 1:end_index
    ]

    if not future:
        return None

    highest = max(
        float(candle["high"])
        for candle in future
    )

    lowest = min(
        float(candle["low"])
        for candle in future
    )

    if signal == "BULLISH":

        mfe = (
            (highest - entry)
            / entry
        ) * 100.0

        mae = (
            (entry - lowest)
            / entry
        ) * 100.0

    else:

        mfe = (
            (entry - lowest)
            / entry
        ) * 100.0

        mae = (
            (highest - entry)
            / entry
        ) * 100.0

    return {
        "mfe": max(mfe, 0.0),
        "mae": max(mae, 0.0),
    }


def early_scalper_signal(
    indicator_state,
    pa_state,
):
    """
    Phase-1 early scalper logic.

    Price action gives structural direction.
    Momentum / ATR / RSI / Stochastic provide confirmation.

    We deliberately do not require every indicator to agree.
    """

    bull_score = 0
    bear_score = 0

    # ===== PRICE ACTION =====

    if pa_state.get("REJECTION") == "BULLISH":
        bull_score += 2

    if pa_state.get("REJECTION") == "BEARISH":
        bear_score += 2

    if pa_state.get("STRUCTURE") == "BULLISH":
        bull_score += 2

    if pa_state.get("STRUCTURE") == "BEARISH":
        bear_score += 2

    if pa_state.get("SWING_BREAK") == "BULLISH":
        bull_score += 1

    if pa_state.get("SWING_BREAK") == "BEARISH":
        bear_score += 1

    # ===== FAST INDICATOR CONFIRMATION =====

    if indicator_state.get("MOMENTUM") == "BULLISH":
        bull_score += 2

    if indicator_state.get("MOMENTUM") == "BEARISH":
        bear_score += 2

    if indicator_state.get("RSI") == "BULLISH":
        bull_score += 1

    if indicator_state.get("RSI") == "BEARISH":
        bear_score += 1

    if indicator_state.get("STOCHASTIC") == "BULLISH":
        bull_score += 1

    if indicator_state.get("STOCHASTIC") == "BEARISH":
        bear_score += 1

    # ATR in existing research is directional state.
    if indicator_state.get("ATR") == "BULLISH":
        bull_score += 1

    if indicator_state.get("ATR") == "BEARISH":
        bear_score += 1

    # Require a meaningful score difference.
    if bull_score >= 5 and bull_score >= bear_score + 2:
        return "BULLISH", bull_score, bear_score

    if bear_score >= 5 and bear_score >= bull_score + 2:
        return "BEARISH", bull_score, bear_score

    return None, bull_score, bear_score



# ============================================================
# PHASE-2A INDIVIDUAL MICROSTRUCTURE FEATURE BACKTEST
# ============================================================

MICRO_FEATURES = [
    "COMPRESSION_EXPANSION",
    "FAILED_BREAK",
    "HIGH_LOW_PROGRESSION",
    "CLOSE_LOCATION",
    "MICRO_STRUCTURE_BREAK",
]


def research_microstructure_features(
    candles,
    micro_states,
):
    """
    Test each microstructure feature independently.

    Output:
    - Signal count
    - Directional win rate
    - Average MFE
    - Average MAE
    - MFE/MAE ratio

    For forward windows:
    1, 2, 3 and 5 candles.
    """

    feature_results = {}

    for feature in MICRO_FEATURES:

        feature_results[feature] = {}

        for window in FORWARD_WINDOWS:

            feature_results[feature][window] = {
                "total": 0,
                "correct": 0,
                "mfe_sum": 0.0,
                "mae_sum": 0.0,
                "excursion_count": 0,
            }

    for i in range(len(candles)):

        state = micro_states[i]

        for feature in MICRO_FEATURES:

            signal = state.get(feature)

            if signal not in (
                "BULLISH",
                "BEARISH",
            ):
                continue

            for window in FORWARD_WINDOWS:

                result = feature_results[
                    feature
                ][window]

                outcome = future_outcome(
                    candles,
                    i,
                    window,
                )

                if (
                    outcome
                    and outcome["direction"] != "FLAT"
                ):
                    result["total"] += 1

                    if (
                        outcome["direction"]
                        == signal
                    ):
                        result["correct"] += 1

                excursion = calculate_mfe_mae(
                    candles,
                    i,
                    window,
                    signal,
                )

                if excursion:

                    result[
                        "excursion_count"
                    ] += 1

                    result[
                        "mfe_sum"
                    ] += excursion["mfe"]

                    result[
                        "mae_sum"
                    ] += excursion["mae"]

    print()
    print("=" * 80)
    print(
        "PHASE-2A INDIVIDUAL "
        "MICROSTRUCTURE FEATURE RESULTS"
    )
    print("=" * 80)

    for feature in MICRO_FEATURES:

        print()
        print("FEATURE:", feature)
        print("-" * 80)

        for window in FORWARD_WINDOWS:

            result = feature_results[
                feature
            ][window]

            total = result["total"]
            correct = result["correct"]

            win_rate = (
                correct / total * 100
                if total
                else 0
            )

            ex_count = result[
                "excursion_count"
            ]

            avg_mfe = (
                result["mfe_sum"]
                / ex_count
                if ex_count
                else 0
            )

            avg_mae = (
                result["mae_sum"]
                / ex_count
                if ex_count
                else 0
            )

            edge_ratio = (
                avg_mfe / avg_mae
                if avg_mae > 0
                else 0
            )

            print(
                f"{window} CANDLE | "
                f"SIGNALS {total} | "
                f"CORRECT {correct} | "
                f"WIN RATE {win_rate:.2f}% | "
                f"MFE {avg_mfe:.4f}% | "
                f"MAE {avg_mae:.4f}% | "
                f"RATIO {edge_ratio:.2f}"
            )

    return feature_results



# ============================================================
# PHASE-2B SEQUENCE / COMBINATION RESEARCH
# ============================================================

SEQUENCE_SETUPS = [
    "FAILED_BREAK_TO_MICRO_BREAK",
    "PROGRESSION_TO_MICRO_BREAK",
    "COMPRESSION_TO_MICRO_BREAK",
]


def recent_matching_signal(
    micro_states,
    i,
    feature,
    direction,
    lookback=3,
):
    """
    Search recent completed candles for a precursor
    matching the current trigger direction.
    """

    start = max(0, i - lookback)

    for j in range(start, i):
        if micro_states[j].get(feature) == direction:
            return True

    return False


def get_sequence_signals(
    micro_states,
    i,
):
    """
    Current MICRO_STRUCTURE_BREAK is the trigger.

    Earlier candle behavior acts as precursor.
    """

    current_direction = micro_states[i].get(
        "MICRO_STRUCTURE_BREAK"
    )

    if current_direction not in (
        "BULLISH",
        "BEARISH",
    ):
        return {}

    signals = {}

    if recent_matching_signal(
        micro_states,
        i,
        "FAILED_BREAK",
        current_direction,
    ):
        signals[
            "FAILED_BREAK_TO_MICRO_BREAK"
        ] = current_direction

    if recent_matching_signal(
        micro_states,
        i,
        "HIGH_LOW_PROGRESSION",
        current_direction,
    ):
        signals[
            "PROGRESSION_TO_MICRO_BREAK"
        ] = current_direction

    if recent_matching_signal(
        micro_states,
        i,
        "COMPRESSION_EXPANSION",
        current_direction,
    ):
        signals[
            "COMPRESSION_TO_MICRO_BREAK"
        ] = current_direction

    return signals


def research_sequence_setups(
    candles,
    micro_states,
):

    results = {
        setup: {
            window: {
                "total": 0,
                "correct": 0,
                "mfe_sum": 0.0,
                "mae_sum": 0.0,
                "excursion_count": 0,
            }
            for window in FORWARD_WINDOWS
        }
        for setup in SEQUENCE_SETUPS
    }

    raw_counts = {
        setup: 0
        for setup in SEQUENCE_SETUPS
    }

    for i in range(len(candles)):

        signals = get_sequence_signals(
            micro_states,
            i,
        )

        for setup, signal in signals.items():

            raw_counts[setup] += 1

            for window in FORWARD_WINDOWS:

                result = results[
                    setup
                ][window]

                outcome = future_outcome(
                    candles,
                    i,
                    window,
                )

                if (
                    outcome
                    and outcome["direction"] != "FLAT"
                ):
                    result["total"] += 1

                    if outcome["direction"] == signal:
                        result["correct"] += 1

                excursion = calculate_mfe_mae(
                    candles,
                    i,
                    window,
                    signal,
                )

                if excursion:

                    result[
                        "excursion_count"
                    ] += 1

                    result[
                        "mfe_sum"
                    ] += excursion["mfe"]

                    result[
                        "mae_sum"
                    ] += excursion["mae"]

    print()
    print("=" * 80)
    print("PHASE-2B SEQUENCE / COMBINATION RESULTS")
    print("=" * 80)

    for setup in SEQUENCE_SETUPS:

        print()
        print(
            "SETUP:",
            setup,
            "| RAW SIGNALS:",
            raw_counts[setup],
        )
        print("-" * 80)

        for window in FORWARD_WINDOWS:

            result = results[
                setup
            ][window]

            total = result["total"]
            correct = result["correct"]

            win_rate = (
                correct / total * 100
                if total
                else 0
            )

            count = result[
                "excursion_count"
            ]

            avg_mfe = (
                result["mfe_sum"] / count
                if count
                else 0
            )

            avg_mae = (
                result["mae_sum"] / count
                if count
                else 0
            )

            ratio = (
                avg_mfe / avg_mae
                if avg_mae > 0
                else 0
            )

            print(
                f"{window} CANDLE | "
                f"SIGNALS {total} | "
                f"CORRECT {correct} | "
                f"WIN RATE {win_rate:.2f}% | "
                f"MFE {avg_mfe:.4f}% | "
                f"MAE {avg_mae:.4f}% | "
                f"RATIO {ratio:.2f}"
            )

    return results



# ============================================================
# PHASE-2C FILTER + TARGET-FIRST RESEARCH
# ============================================================

PHASE2C_SETUPS = [
    "BASE_COMPRESSION_MICRO",
    "PLUS_CLOSE_LOCATION",
    "PLUS_PROGRESSION",
    "PLUS_MOMENTUM",
]


def target_before_stop(
    candles,
    index,
    direction,
    window,
    target_pct,
    stop_pct,
):
    """
    Simulate whether target or stop is touched first
    after signal candle close.

    Conservative rule:
    If target and stop are both touched inside the same
    future candle, count STOP first because intrabar order
    cannot be known from OHLC data.
    """

    if direction not in ("BULLISH", "BEARISH"):
        return None

    entry = float(candles[index]["close"])

    if entry <= 0:
        return None

    end = min(
        index + window + 1,
        len(candles),
    )

    for j in range(index + 1, end):

        high = float(candles[j]["high"])
        low = float(candles[j]["low"])

        if direction == "BULLISH":

            target_price = entry * (
                1 + target_pct / 100.0
            )

            stop_price = entry * (
                1 - stop_pct / 100.0
            )

            target_hit = high >= target_price
            stop_hit = low <= stop_price

        else:

            target_price = entry * (
                1 - target_pct / 100.0
            )

            stop_price = entry * (
                1 + stop_pct / 100.0
            )

            target_hit = low <= target_price
            stop_hit = high >= stop_price

        # Conservative OHLC handling
        if target_hit and stop_hit:
            return "STOP"

        if stop_hit:
            return "STOP"

        if target_hit:
            return "TARGET"

    return "NONE"


def get_phase2c_signals(
    micro_states,
    indicator_states,
    i,
):
    """
    Base trigger:
    Recent compression/expansion aligned with
    current micro structure break.

    Then test filters independently.
    """

    direction = micro_states[i].get(
        "MICRO_STRUCTURE_BREAK"
    )

    if direction not in (
        "BULLISH",
        "BEARISH",
    ):
        return {}

    has_compression = recent_matching_signal(
        micro_states,
        i,
        "COMPRESSION_EXPANSION",
        direction,
    )

    if not has_compression:
        return {}

    signals = {
        "BASE_COMPRESSION_MICRO":
            direction
    }

    if (
        micro_states[i].get(
            "CLOSE_LOCATION"
        )
        == direction
    ):
        signals[
            "PLUS_CLOSE_LOCATION"
        ] = direction

    if recent_matching_signal(
        micro_states,
        i,
        "HIGH_LOW_PROGRESSION",
        direction,
    ):
        signals[
            "PLUS_PROGRESSION"
        ] = direction

    if (
        indicator_states[i].get(
            "MOMENTUM"
        )
        == direction
    ):
        signals[
            "PLUS_MOMENTUM"
        ] = direction

    return signals


def research_phase2c(
    candles,
    micro_states,
    indicator_states,
):
    """
    Test promising compression -> micro break setup
    with additional filters.

    Target/SL percentages are SPOT movement,
    not option premium percentages.
    """

    target_stop_tests = [
        (0.05, 0.05),
        (0.10, 0.05),
        (0.10, 0.10),
        (0.15, 0.10),
    ]

    window = 5

    results = {}

    for setup in PHASE2C_SETUPS:

        results[setup] = {
            "signals": 0,
            "mfe_sum": 0.0,
            "mae_sum": 0.0,
            "excursion_count": 0,
            "tests": {
                pair: {
                    "target": 0,
                    "stop": 0,
                    "none": 0,
                }
                for pair in target_stop_tests
            },
        }

    for i in range(len(candles)):

        signals = get_phase2c_signals(
            micro_states,
            indicator_states,
            i,
        )

        for setup, direction in signals.items():

            result = results[setup]

            result["signals"] += 1

            excursion = calculate_mfe_mae(
                candles,
                i,
                window,
                direction,
            )

            if excursion:

                result[
                    "excursion_count"
                ] += 1

                result[
                    "mfe_sum"
                ] += excursion["mfe"]

                result[
                    "mae_sum"
                ] += excursion["mae"]

            for pair in target_stop_tests:

                target_pct, stop_pct = pair

                outcome = target_before_stop(
                    candles,
                    i,
                    direction,
                    window,
                    target_pct,
                    stop_pct,
                )

                if outcome == "TARGET":
                    result["tests"][pair][
                        "target"
                    ] += 1

                elif outcome == "STOP":
                    result["tests"][pair][
                        "stop"
                    ] += 1

                else:
                    result["tests"][pair][
                        "none"
                    ] += 1

    print()
    print("=" * 80)
    print(
        "PHASE-2C FILTER + TARGET-FIRST RESULTS"
    )
    print("=" * 80)

    for setup in PHASE2C_SETUPS:

        result = results[setup]

        count = result[
            "excursion_count"
        ]

        avg_mfe = (
            result["mfe_sum"] / count
            if count
            else 0
        )

        avg_mae = (
            result["mae_sum"] / count
            if count
            else 0
        )

        ratio = (
            avg_mfe / avg_mae
            if avg_mae > 0
            else 0
        )

        print()
        print(
            "SETUP:",
            setup,
            "| SIGNALS:",
            result["signals"],
            "| 5C MFE:",
            f"{avg_mfe:.4f}%",
            "| 5C MAE:",
            f"{avg_mae:.4f}%",
            "| RATIO:",
            f"{ratio:.2f}",
        )

        print("-" * 80)

        for pair in target_stop_tests:

            target_pct, stop_pct = pair

            test = result[
                "tests"
            ][pair]

            target = test["target"]
            stop = test["stop"]
            none = test["none"]

            resolved = target + stop

            target_rate = (
                target / resolved * 100
                if resolved
                else 0
            )

            print(
                f"TARGET {target_pct:.2f}% | "
                f"SL {stop_pct:.2f}% | "
                f"TARGET-FIRST {target} | "
                f"STOP-FIRST {stop} | "
                f"NONE {none} | "
                f"RESOLVED WIN RATE "
                f"{target_rate:.2f}%"
            )

    return results




# ============================================================
# PHASE-2F REGIME + TIME-OF-DAY RESEARCH
# Base: Compression + Progression -> Micro Structure Break
# Compare BASE vs PLUS_ATR
# Target 0.10% / SL 0.10%, forward windows 3C and 5C
# ============================================================

def phase2f_time_bucket(value):
    """
    Convert candle time to intraday session bucket.

    Expected common formats include:
    YYYY-MM-DD HH:MM:SS
    YYYY-MM-DDTHH:MM:SS
    HH:MM:SS

    Falls back to UNKNOWN if time cannot be parsed.
    """
    if value is None:
        return "UNKNOWN"

    value = str(value).strip()

    try:
        time_part = value.split("T")[-1] if "T" in value else value.split()[-1]
        hour_minute = time_part[:5]
        hour, minute = map(int, hour_minute.split(":"))
        minutes = hour * 60 + minute
    except (ValueError, TypeError, IndexError):
        return "UNKNOWN"

    # Indian cash-market intraday segmentation
    # MORNING   : 09:15 - 10:30
    # MIDDAY    : 10:30 - 13:30
    # AFTERNOON : 13:30 - market close
    if 9 * 60 + 15 <= minutes < 10 * 60 + 30:
        return "MORNING"

    if 10 * 60 + 30 <= minutes < 13 * 60 + 30:
        return "MIDDAY"

    if 13 * 60 + 30 <= minutes <= 15 * 60 + 30:
        return "AFTERNOON"

    return "UNKNOWN"


def research_phase2f_regime_time(
    candles,
    micro_states,
    indicator_states,
):
    """
    Phase-2F research.

    Structural trigger:
        Compression + High/Low Progression
        -> Micro Structure Break

    Regime:
        TREND:
            EMA state agrees with signal direction.

        RANGE_OTHER:
            EMA is NEUTRAL or disagrees with signal direction.

    Filters:
        BASE
        PLUS_ATR

    Evaluation:
        Target 0.10%
        Stop   0.10%
        Forward windows 3 and 5 candles.
    """

    windows = [3, 5]
    target_pct = 0.10
    stop_pct = 0.10

    directions = [
        "BULLISH",
        "BEARISH",
    ]

    regimes = [
        "TREND",
        "RANGE_OTHER",
    ]

    sessions = [
        "ALL",
        "MORNING",
        "MIDDAY",
        "AFTERNOON",
        "UNKNOWN",
    ]

    setups = [
        "BASE",
        "PLUS_ATR",
    ]

    def new_bucket():
        return {
            "signals": 0,
            "target": 0,
            "stop": 0,
            "none": 0,
        }

    results = {}

    for direction in directions:
        results[direction] = {}

        for regime in regimes:
            results[direction][regime] = {}

            for session in sessions:
                results[direction][regime][session] = {}

                for setup in setups:
                    results[direction][regime][session][setup] = {
                        window: new_bucket()
                        for window in windows
                    }

    for i in range(len(candles)):

        direction = micro_states[i].get(
            "MICRO_STRUCTURE_BREAK"
        )

        if direction not in (
            "BULLISH",
            "BEARISH",
        ):
            continue

        has_compression = recent_matching_signal(
            micro_states,
            i,
            "COMPRESSION_EXPANSION",
            direction,
        )

        has_progression = recent_matching_signal(
            micro_states,
            i,
            "HIGH_LOW_PROGRESSION",
            direction,
        )

        if not (
            has_compression
            and has_progression
        ):
            continue

        indicator_state = indicator_states[i]

        ema_state = indicator_state.get(
            "EMA",
            "NEUTRAL",
        )

        if ema_state == direction:
            regime = "TREND"
        else:
            regime = "RANGE_OTHER"

        session = phase2f_time_bucket(
            candles[i].get("time")
        )

        active_setups = [
            "BASE",
        ]

        if (
            indicator_state.get("ATR")
            == direction
        ):
            active_setups.append(
                "PLUS_ATR"
            )

        for setup in active_setups:

            # Record both ALL-session result
            # and exact time bucket.
            active_sessions = ["ALL"]

            if session != "ALL":
                active_sessions.append(
                    session
                )

            for session_key in active_sessions:

                for window in windows:

                    bucket = results[
                        direction
                    ][regime][session_key][setup][
                        window
                    ]

                    bucket["signals"] += 1

                    outcome = target_before_stop(
                        candles,
                        i,
                        direction,
                        window,
                        target_pct,
                        stop_pct,
                    )

                    if outcome == "TARGET":
                        bucket["target"] += 1

                    elif outcome == "STOP":
                        bucket["stop"] += 1

                    else:
                        bucket["none"] += 1

    print()
    print("=" * 80)
    print(
        "PHASE-2F REGIME + TIME-OF-DAY RESEARCH"
    )
    print(
        "BASE: COMPRESSION + PROGRESSION -> MICRO BREAK"
    )
    print(
        "TARGET 0.10% | SL 0.10%"
    )
    print("=" * 80)

    for direction in directions:

        print()
        print(
            "DIRECTION:",
            direction,
        )
        print("=" * 80)

        for regime in regimes:

            print()
            print(
                "REGIME:",
                regime,
            )
            print("-" * 80)

            for session in sessions:

                base_signals = results[
                    direction
                ][regime][session]["BASE"][3][
                    "signals"
                ]

                atr_signals = results[
                    direction
                ][regime][session]["PLUS_ATR"][3][
                    "signals"
                ]

                if (
                    base_signals == 0
                    and atr_signals == 0
                ):
                    continue

                print()
                print(
                    "SESSION:",
                    session,
                )

                for setup in setups:

                    for window in windows:

                        bucket = results[
                            direction
                        ][regime][session][setup][
                            window
                        ]

                        signals = bucket[
                            "signals"
                        ]

                        target = bucket[
                            "target"
                        ]

                        stop = bucket[
                            "stop"
                        ]

                        none = bucket[
                            "none"
                        ]

                        resolved = (
                            target
                            + stop
                        )

                        win_rate = (
                            target
                            / resolved
                            * 100
                            if resolved
                            else 0
                        )

                        resolved_pct = (
                            resolved
                            / signals
                            * 100
                            if signals
                            else 0
                        )

                        print(
                            f"{setup:10s} | "
                            f"{window}C | "
                            f"SIGNALS {signals} | "
                            f"T {target} | "
                            f"S {stop} | "
                            f"NONE {none} | "
                            f"WIN {win_rate:.2f}% | "
                            f"RESOLVED {resolved_pct:.2f}%"
                        )

    return results


# ============================================================
# PHASE-2D DIRECTION-WISE BEST SETUP RESEARCH
# Compression + Progression -> Micro Structure Break
# ============================================================

def research_phase2d_direction(
    candles,
    micro_states,
):

    windows = [1, 2, 3, 5]

    target_stop_tests = [
        (0.05, 0.05),
        (0.10, 0.10),
        (0.15, 0.10),
    ]

    results = {
        direction: {
            window: {
                pair: {
                    "target": 0,
                    "stop": 0,
                    "none": 0,
                }
                for pair in target_stop_tests
            }
            for window in windows
        }
        for direction in (
            "BULLISH",
            "BEARISH",
        )
    }

    signal_counts = {
        "BULLISH": 0,
        "BEARISH": 0,
    }

    for i in range(len(candles)):

        direction = micro_states[i].get(
            "MICRO_STRUCTURE_BREAK"
        )

        if direction not in (
            "BULLISH",
            "BEARISH",
        ):
            continue

        has_compression = recent_matching_signal(
            micro_states,
            i,
            "COMPRESSION_EXPANSION",
            direction,
        )

        has_progression = recent_matching_signal(
            micro_states,
            i,
            "HIGH_LOW_PROGRESSION",
            direction,
        )

        if not (
            has_compression
            and has_progression
        ):
            continue

        signal_counts[direction] += 1

        for window in windows:

            for pair in target_stop_tests:

                target_pct, stop_pct = pair

                outcome = target_before_stop(
                    candles,
                    i,
                    direction,
                    window,
                    target_pct,
                    stop_pct,
                )

                bucket = results[
                    direction
                ][window][pair]

                if outcome == "TARGET":
                    bucket["target"] += 1

                elif outcome == "STOP":
                    bucket["stop"] += 1

                else:
                    bucket["none"] += 1

    print()
    print("=" * 80)
    print(
        "PHASE-2D DIRECTION-WISE BEST SETUP"
    )
    print("=" * 80)

    for direction in (
        "BULLISH",
        "BEARISH",
    ):

        print()
        print(
            "DIRECTION:",
            direction,
            "| SIGNALS:",
            signal_counts[direction],
        )

        print("-" * 80)

        for window in windows:

            print(
                f"FORWARD WINDOW: "
                f"{window} CANDLE"
            )

            for pair in target_stop_tests:

                target_pct, stop_pct = pair

                bucket = results[
                    direction
                ][window][pair]

                target = bucket["target"]
                stop = bucket["stop"]
                none = bucket["none"]

                resolved = target + stop

                win_rate = (
                    target / resolved * 100
                    if resolved
                    else 0
                )

                print(
                    f"TARGET {target_pct:.2f}% | "
                    f"SL {stop_pct:.2f}% | "
                    f"T {target} | "
                    f"S {stop} | "
                    f"NONE {none} | "
                    f"WIN {win_rate:.2f}%"
                )

            print()

    return results



# ============================================================
# PHASE-2E INDICATOR CONFIRMATION FILTER RESEARCH
# Base: Compression + Progression -> Micro Structure Break
# Tests BULLISH / BEARISH separately.
# ============================================================

def research_phase2e_indicator_filters(
    candles,
    micro_states,
    indicator_states,
):
    windows = [3, 5]
    target_pct = 0.10
    stop_pct = 0.10

    setups = [
        "BASE",
        "PLUS_RSI",
        "PLUS_ATR",
        "PLUS_MOMENTUM",
        "PLUS_STOCHASTIC",
        "PLUS_RSI_ATR",
        "PLUS_MOMENTUM_ATR",
    ]

    results = {
        direction: {
            setup: {
                window: {
                    "signals": 0,
                    "target": 0,
                    "stop": 0,
                    "none": 0,
                }
                for window in windows
            }
            for setup in setups
        }
        for direction in ("BULLISH", "BEARISH")
    }

    for i in range(len(candles)):

        direction = micro_states[i].get(
            "MICRO_STRUCTURE_BREAK"
        )

        if direction not in (
            "BULLISH",
            "BEARISH",
        ):
            continue

        # Phase-2D best structural base:
        # Compression + Progression -> Micro Break
        has_compression = recent_matching_signal(
            micro_states,
            i,
            "COMPRESSION_EXPANSION",
            direction,
        )

        has_progression = recent_matching_signal(
            micro_states,
            i,
            "HIGH_LOW_PROGRESSION",
            direction,
        )

        if not (
            has_compression
            and has_progression
        ):
            continue

        ind = indicator_states[i]

        active_setups = ["BASE"]

        if ind.get("RSI") == direction:
            active_setups.append(
                "PLUS_RSI"
            )

        if ind.get("ATR") == direction:
            active_setups.append(
                "PLUS_ATR"
            )

        if ind.get("MOMENTUM") == direction:
            active_setups.append(
                "PLUS_MOMENTUM"
            )

        if ind.get("STOCHASTIC") == direction:
            active_setups.append(
                "PLUS_STOCHASTIC"
            )

        if (
            ind.get("RSI") == direction
            and ind.get("ATR") == direction
        ):
            active_setups.append(
                "PLUS_RSI_ATR"
            )

        if (
            ind.get("MOMENTUM") == direction
            and ind.get("ATR") == direction
        ):
            active_setups.append(
                "PLUS_MOMENTUM_ATR"
            )

        for setup in active_setups:

            for window in windows:

                bucket = results[
                    direction
                ][setup][window]

                bucket["signals"] += 1

                outcome = target_before_stop(
                    candles,
                    i,
                    direction,
                    window,
                    target_pct,
                    stop_pct,
                )

                if outcome == "TARGET":
                    bucket["target"] += 1

                elif outcome == "STOP":
                    bucket["stop"] += 1

                else:
                    bucket["none"] += 1

    print()
    print("=" * 80)
    print(
        "PHASE-2E INDICATOR CONFIRMATION FILTERS"
    )
    print(
        "BASE: COMPRESSION + PROGRESSION -> MICRO BREAK"
    )
    print(
        "TARGET 0.10% | SL 0.10%"
    )
    print("=" * 80)

    for direction in (
        "BULLISH",
        "BEARISH",
    ):

        print()
        print(
            "DIRECTION:",
            direction,
        )
        print("-" * 80)

        for setup in setups:

            print()
            print(
                "SETUP:",
                setup,
            )

            for window in windows:

                bucket = results[
                    direction
                ][setup][window]

                signals = bucket["signals"]
                target = bucket["target"]
                stop = bucket["stop"]
                none = bucket["none"]

                resolved = (
                    target + stop
                )

                win_rate = (
                    target
                    / resolved
                    * 100
                    if resolved
                    else 0
                )

                coverage = (
                    resolved
                    / signals
                    * 100
                    if signals
                    else 0
                )

                print(
                    f"{window} CANDLE | "
                    f"SIGNALS {signals} | "
                    f"T {target} | "
                    f"S {stop} | "
                    f"NONE {none} | "
                    f"WIN {win_rate:.2f}% | "
                    f"RESOLVED {coverage:.2f}%"
                )

    return results



def fetch_large_history(
    m,
    segment,
    token,
    interval,
    chunk_days,
    max_candles=5000,
):
    all_rows = []
    cursor_end = datetime.now()
    loops = 0
    max_loops = 300

    while len(all_rows) < max_candles and loops < max_loops:
        loops += 1

        cursor_start = cursor_end - timedelta(days=chunk_days)

        try:
            rows = fetch_chunk(
                m,
                segment,
                token,
                interval,
                cursor_start.strftime("%Y-%m-%d"),
                cursor_end.strftime("%Y-%m-%d"),
            )
        except Exception as e:
            print(
                "LARGE HISTORY FETCH ERROR",
                interval,
                cursor_start.strftime("%Y-%m-%d"),
                cursor_end.strftime("%Y-%m-%d"),
                type(e).__name__,
                e,
            )
            rows = []

        if rows:
            all_rows.extend(rows)

        cursor_end = cursor_start - timedelta(days=1)

    unique = {
        row[0]: row
        for row in all_rows
        if row
    }

    rows = sorted(
        unique.values(),
        key=lambda x: x[0],
    )

    if len(rows) > max_candles:
        rows = rows[-max_candles:]

    return rows


def research_index(api, index_name):
    cfg = CONFIG[index_name]

    rows = fetch_large_history(
        api,
        cfg["segment"],
        cfg["token"],
        TIMEFRAMES["5M"]["api_interval"],
        TIMEFRAMES["5M"]["chunk_days"],
        max_candles=5000,
    )

    candles = prepare_candles(rows)

    print()
    print("=" * 80)
    print("SCALPER RESEARCH:", index_name)
    print("CANDLES:", len(candles))
    print("=" * 80)

    if len(candles) < 100:
        print("INSUFFICIENT CANDLES")
        return

    indicator_states = build_indicator_states(
        candles
    )

    pa_states = build_price_action_states(
        candles
    )

    # ===== PHASE-2A MICROSTRUCTURE STATES =====
    micro_states = build_microstructure_states(
        candles
    )

    results = {
        window: create_stats()
        for window in FORWARD_WINDOWS
    }

    # ===== PHASE-2 MFE / MAE STORAGE =====
    excursion_results = {
        window: {
            "count": 0,
            "mfe_sum": 0.0,
            "mae_sum": 0.0,
        }
        for window in FORWARD_WINDOWS
    }

    score_distribution = defaultdict(int)

    # Score-wise forward performance
    score_results = defaultdict(
        lambda: {
            window: create_stats()
            for window in FORWARD_WINDOWS
        }
    )

    signal_count = 0

    for i in range(len(candles)):

        signal, bull_score, bear_score = early_scalper_signal(
            indicator_states[i],
            pa_states[i],
        )

        if signal is None:
            continue

        signal_count += 1

        active_score = (
            bull_score
            if signal == "BULLISH"
            else bear_score
        )

        score_distribution[
            active_score
        ] += 1

        for window in FORWARD_WINDOWS:

            outcome = future_outcome(
                candles,
                i,
                window,
            )

            excursion = calculate_mfe_mae(
                candles,
                i,
                window,
                signal,
            )

            if excursion:
                excursion_results[window]["count"] += 1
                excursion_results[window]["mfe_sum"] += excursion["mfe"]
                excursion_results[window]["mae_sum"] += excursion["mae"]

            update_stats(
                results[window],
                signal,
                outcome,
            )

            update_stats(
                score_results[active_score][window],
                signal,
                outcome,
            )

    # ===== PHASE-2A INDIVIDUAL FEATURE TEST =====
    research_microstructure_features(
        candles,
        micro_states,
    )

    # ===== PHASE-2B SEQUENCE TEST =====
    research_sequence_setups(
        candles,
        micro_states,
    )

    # ===== PHASE-2C FILTER / TARGET-FIRST TEST =====
    research_phase2c(
        candles,
        micro_states,
        indicator_states,
    )

    # ===== PHASE-2F REGIME + TIME-OF-DAY TEST =====
    phase2f_results = research_phase2f_regime_time(
        candles,
        micro_states,
        indicator_states,
    )


    # ===== PHASE-3 FOCUSED BEST-POCKET TEST =====
    print()
    print("=" * 80)
    print("PHASE-3 FOCUSED BEST POCKETS:", index_name)
    print("TARGET 0.10% | SL 0.10% | MIN SIGNALS 10")
    print("=" * 80)

    phase3_rows = []

    for direction in ("BULLISH", "BEARISH"):
        for regime in ("TREND", "RANGE_OTHER"):
            for session in ("MORNING", "MIDDAY", "AFTERNOON"):
                for setup in ("BASE", "PLUS_ATR"):
                    for window in (3, 5):
                        bucket = phase2f_results[
                            direction
                        ][regime][session][setup][window]

                        signals = bucket["signals"]
                        target = bucket["target"]
                        stop = bucket["stop"]
                        none = bucket["none"]
                        resolved = target + stop

                        if signals < 10 or resolved == 0:
                            continue

                        win_rate = target / resolved * 100
                        resolved_pct = resolved / signals * 100

                        phase3_rows.append((
                            win_rate,
                            resolved_pct,
                            signals,
                            direction,
                            regime,
                            session,
                            setup,
                            window,
                            target,
                            stop,
                            none,
                        ))

    phase3_rows.sort(
        key=lambda x: (x[0], x[1], x[2]),
        reverse=True,
    )

    for rank, row in enumerate(phase3_rows[:15], 1):
        (
            win_rate,
            resolved_pct,
            signals,
            direction,
            regime,
            session,
            setup,
            window,
            target,
            stop,
            none,
        ) = row

        print(
            f"#{rank:02d} | "
            f"{direction} | "
            f"{regime} | "
            f"{session} | "
            f"{setup} | "
            f"{window}C | "
            f"SIGNALS {signals} | "
            f"T {target} | "
            f"S {stop} | "
            f"NONE {none} | "
            f"WIN {win_rate:.2f}% | "
            f"RESOLVED {resolved_pct:.2f}%"
        )

    # ===== PHASE-2D DIRECTION TEST =====
    research_phase2d_direction(
        candles,
        micro_states,
    )

    # ===== PHASE-2E INDICATOR CONFIRMATION TEST =====
    research_phase2e_indicator_filters(
        candles,
        micro_states,
        indicator_states,
    )

    print()
    print("=" * 80)
    print("ORIGINAL SCALPER SCORE RESULTS")
    print("=" * 80)

    print("TOTAL RAW SIGNALS:", signal_count)

    print()
    print("FORWARD PERFORMANCE")
    print("-" * 80)

    for window in FORWARD_WINDOWS:

        stats = results[window]

        total = stats["total"]
        correct = stats["correct"]

        win_rate = (
            correct / total * 100
            if total
            else 0
        )

        avg_move = (
            stats["move_sum"] / total
            if total
            else 0
        )

        print(
            f"{window} CANDLE | "
            f"SIGNALS {total} | "
            f"CORRECT {correct} | "
            f"WIN RATE {win_rate:.2f}% | "
            f"AVG MOVE {avg_move:.4f}%"
        )

    print()
    print("MFE / MAE PERFORMANCE")
    print("-" * 80)

    for window in FORWARD_WINDOWS:

        ex = excursion_results[window]

        count = ex["count"]

        avg_mfe = (
            ex["mfe_sum"] / count
            if count
            else 0
        )

        avg_mae = (
            ex["mae_sum"] / count
            if count
            else 0
        )

        edge_ratio = (
            avg_mfe / avg_mae
            if avg_mae > 0
            else 0
        )

        print(
            f"{window} CANDLE | "
            f"SAMPLES {count} | "
            f"AVG MFE {avg_mfe:.4f}% | "
            f"AVG MAE {avg_mae:.4f}% | "
            f"MFE/MAE {edge_ratio:.2f}"
        )

    print()
    print("SCORE DISTRIBUTION")
    print("-" * 80)

    for score in sorted(
        score_distribution
    ):
        print(
            "SCORE",
            score,
            "| SIGNALS",
            score_distribution[score],
        )

    print()
    print("SCORE-WISE FORWARD PERFORMANCE")
    print("-" * 80)

    for score in sorted(score_results):

        print()
        print("SCORE:", score)

        for window in FORWARD_WINDOWS:

            stats = score_results[score][window]

            total = stats["total"]
            correct = stats["correct"]

            win_rate = (
                correct / total * 100
                if total
                else 0
            )

            avg_move = (
                stats["move_sum"] / total
                if total
                else 0
            )

            print(
                f"  {window} CANDLE | "
                f"SIGNALS {total} | "
                f"CORRECT {correct} | "
                f"WIN RATE {win_rate:.2f}% | "
                f"AVG MOVE {avg_move:.4f}%"
            )


def main():
    from historical.indicator_combination_research import (
        load_api,
    )

    api = load_api()

    for index_name in [
        "NIFTY",
        "SENSEX",
    ]:
        research_index(
            api,
            index_name,
        )


if __name__ == "__main__":
    main()
