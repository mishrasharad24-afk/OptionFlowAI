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
