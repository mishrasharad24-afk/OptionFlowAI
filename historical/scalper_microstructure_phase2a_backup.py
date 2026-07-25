"""
SCALPER MODE RESEARCH - PHASE 1

Goal:
Detect early intraday directional moves on 5M candles.

This research file is independent from the live bot.
It reuses the existing 950-candle historical infrastructure.
"""

from collections import defaultdict

from historical.multi_timeframe_research import (
    CONFIG,
    TIMEFRAMES,
    fetch_max_950,
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


def research_index(api, index_name):
    cfg = CONFIG[index_name]

    rows = fetch_max_950(
        api,
        cfg["segment"],
        cfg["token"],
        TIMEFRAMES["5M"]["api_interval"],
        TIMEFRAMES["5M"]["chunk_days"],
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
