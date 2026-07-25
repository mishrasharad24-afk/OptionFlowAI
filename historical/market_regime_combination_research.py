import sys
import os
import traceback
from collections import defaultdict

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY

from historical.multi_timeframe_research import (
    TOKEN_FILE,
    MAX_CANDLES,
    CONFIG,
    TIMEFRAMES,
    fetch_max_950,
)

from historical.indicator_combination_research import (
    prepare_candles,
    build_indicator_states,
    get_combinations,
    cross_timeframe_combinations,
    build_15m_state_map,
    get_15m_state_for_5m,
    future_outcome,
    update_stats,
    create_stats,
)


# ============================================================
# MARKET REGIME + INDICATOR COMBINATION RESEARCH
#
# INDEX:
#   NIFTY
#   SENSEX
#
# TIMEFRAMES:
#   5M
#   15M
#   5M + 15M
#
# PURPOSE:
#   Find which indicator combination works best
#   under different market regimes.
#
# RESEARCH ONLY.
# THIS SCRIPT DOES NOT PLACE TRADES.
# ============================================================

MIN_SAMPLE_SIZE = 20

FUTURE_WINDOWS = [
    1,
    3,
    5,
]

RESEARCH_TIMEFRAMES = [
    "5M",
    "15M",
]


def safe_float(
    value,
    default=0.0
):
    try:
        return float(value)
    except Exception:
        return default


def merge_results(
    target,
    source
):
    for key, stats in source.items():

        target_stats = target[
            key
        ]

        for field in (
            "total",
            "correct",
            "bullish",
            "bearish",
            "bull_correct",
            "bear_correct",
        ):

            target_stats[
                field
            ] += stats[
                field
            ]

        target_stats[
            "move_sum"
        ] += stats[
            "move_sum"
        ]


def candle_direction(
    candle
):
    open_price = safe_float(
        candle["open"]
    )

    close_price = safe_float(
        candle["close"]
    )

    if close_price > open_price:
        return "BULLISH"

    if close_price < open_price:
        return "BEARISH"

    return "FLAT"


def calculate_change_pct(
    old_price,
    new_price
):
    old_price = safe_float(
        old_price
    )

    new_price = safe_float(
        new_price
    )

    if old_price <= 0:
        return 0.0

    return (
        (
            new_price
            - old_price
        )
        / old_price
    ) * 100.0


def detect_local_regime(
    candles,
    index,
    lookback=12
):
    if index < lookback:
        return "UNKNOWN"

    current_close = candles[
        index
    ][
        "close"
    ]

    old_close = candles[
        index - lookback
    ][
        "close"
    ]

    change_pct = calculate_change_pct(
        old_close,
        current_close
    )

    recent = candles[
        index - lookback + 1:
        index + 1
    ]

    bullish_candles = sum(
        1
        for candle in recent
        if candle_direction(
            candle
        ) == "BULLISH"
    )

    bearish_candles = sum(
        1
        for candle in recent
        if candle_direction(
            candle
        ) == "BEARISH"
    )

    total = len(
        recent
    )

    if total <= 0:
        return "UNKNOWN"

    bull_ratio = (
        bullish_candles
        / total
    )

    bear_ratio = (
        bearish_candles
        / total
    )

    if (
        change_pct >= 0.30
        and bull_ratio >= 0.58
    ):
        return "BULL_TREND"

    if (
        change_pct <= -0.30
        and bear_ratio >= 0.58
    ):
        return "BEAR_TREND"

    if abs(
        change_pct
    ) <= 0.15:
        return "SIDEWAYS"

    if change_pct > 0:
        return "BULL_MIXED"

    if change_pct < 0:
        return "BEAR_MIXED"

    return "SIDEWAYS"


def regime_key(
    timeframe,
    regime,
    combination,
    window
):
    return (
        timeframe,
        regime,
        combination,
        window,
    )
def research_regime_single_timeframe(
    candles,
    states,
    timeframe
):
    results = defaultdict(
        create_stats
    )

    regime_counts = defaultdict(
        int
    )

    for i in range(
        len(candles)
    ):

        regime = detect_local_regime(
            candles,
            i
        )

        if regime == "UNKNOWN":
            continue

        regime_counts[
            regime
        ] += 1

        combinations = get_combinations(
            states[i]
        )

        for (
            combination,
            signal
        ) in combinations.items():

            if signal is None:
                continue

            for window in FUTURE_WINDOWS:

                outcome = future_outcome(
                    candles,
                    i,
                    window
                )

                key = regime_key(
                    timeframe,
                    regime,
                    combination,
                    window
                )

                update_stats(
                    results[key],
                    signal,
                    outcome
                )

    print(
        f"\nREGIME COUNTS: {timeframe}"
    )

    for (
        regime,
        count
    ) in sorted(
        regime_counts.items()
    ):

        print(
            f"{regime:<15} | "
            f"CANDLES {count}"
        )

    return results


def research_regime_cross_timeframe(
    candles_5m,
    states_5m,
    candles_15m,
    states_15m
):
    results = defaultdict(
        create_stats
    )

    state_map_15m = build_15m_state_map(
        candles_15m,
        states_15m
    )

    matched = 0

    regime_counts = defaultdict(
        int
    )

    for i in range(
        len(candles_5m)
    ):

        state_15m = get_15m_state_for_5m(
            candles_5m[i],
            state_map_15m
        )

        if state_15m is None:
            continue

        matched += 1

        regime = detect_local_regime(
            candles_5m,
            i
        )

        if regime == "UNKNOWN":
            continue

        regime_counts[
            regime
        ] += 1

        state_5m = states_5m[
            i
        ]

        combinations = (
            cross_timeframe_combinations(
                state_5m,
                state_15m
            )
        )

        for (
            combination,
            signal
        ) in combinations.items():

            if signal is None:
                continue

            for window in FUTURE_WINDOWS:

                outcome = future_outcome(
                    candles_5m,
                    i,
                    window
                )

                key = regime_key(
                    "5M+15M",
                    regime,
                    combination,
                    window
                )

                update_stats(
                    results[key],
                    signal,
                    outcome
                )

    print(
        "\n5M + 15M MATCHED CANDLES:",
        matched
    )

    print(
        "5M + 15M REGIME COUNTS:"
    )

    for (
        regime,
        count
    ) in sorted(
        regime_counts.items()
    ):

        print(
            f"{regime:<15} | "
            f"CANDLES {count}"
        )

    return results


def calculate_metrics(
    stats
):
    total = stats[
        "total"
    ]

    if total <= 0:
        return None

    accuracy = (
        stats[
            "correct"
        ]
        / total
    ) * 100.0

    bullish = stats[
        "bullish"
    ]

    bearish = stats[
        "bearish"
    ]

    if bullish > 0:

        bull_accuracy = (
            stats[
                "bull_correct"
            ]
            / bullish
        ) * 100.0

    else:

        bull_accuracy = 0.0

    if bearish > 0:

        bear_accuracy = (
            stats[
                "bear_correct"
            ]
            / bearish
        ) * 100.0

    else:

        bear_accuracy = 0.0

    avg_move = (
        stats[
            "move_sum"
        ]
        / total
    )

    return {
        "accuracy": accuracy,
        "total": total,
        "bull_accuracy": bull_accuracy,
        "bear_accuracy": bear_accuracy,
        "avg_move": avg_move,
    }


def build_ranked_results(
    results
):
    ranked = []

    for (
        key,
        stats
    ) in results.items():

        metrics = calculate_metrics(
            stats
        )

        if metrics is None:
            continue

        if (
            metrics["total"]
            < MIN_SAMPLE_SIZE
        ):
            continue

        (
            timeframe,
            regime,
            combination,
            window,
        ) = key

        ranked.append(
            (
                metrics[
                    "accuracy"
                ],
                metrics[
                    "total"
                ],
                timeframe,
                regime,
                combination,
                window,
                metrics[
                    "bull_accuracy"
                ],
                metrics[
                    "bear_accuracy"
                ],
                metrics[
                    "avg_move"
                ],
            )
        )

    ranked.sort(
        key=lambda row: (
            row[0],
            row[1],
        ),
        reverse=True
    )

    return ranked
def print_ranked_results(
    title,
    results,
    limit=30
):
    print(
        "\n"
        + "=" * 120
    )

    print(
        title
    )

    ranked = build_ranked_results(
        results
    )

    if not ranked:

        print(
            "NO QUALIFIED RESULTS"
        )

        return []

    for row in ranked[
        :limit
    ]:

        (
            accuracy,
            total,
            timeframe,
            regime,
            combination,
            window,
            bull_accuracy,
            bear_accuracy,
            avg_move,
        ) = row

        print(
            f"{timeframe:<7} | "
            f"{regime:<12} | "
            f"{combination:<50} | "
            f"NEXT {window:<2} | "
            f"SAMPLES {total:<4} | "
            f"ACC {accuracy:6.2f}% | "
            f"BULL {bull_accuracy:6.2f}% | "
            f"BEAR {bear_accuracy:6.2f}% | "
            f"AVG MOVE {avg_move:.3f}%"
        )

    return ranked


def print_best_by_regime(
    title,
    results,
    limit_per_regime=10
):
    print(
        "\n"
        + "=" * 120
    )

    print(
        title
    )

    ranked = build_ranked_results(
        results
    )

    if not ranked:

        print(
            "NO QUALIFIED RESULTS"
        )

        return

    grouped = defaultdict(
        list
    )

    for row in ranked:

        regime = row[
            3
        ]

        grouped[
            regime
        ].append(
            row
        )

    for regime in sorted(
        grouped.keys()
    ):

        print(
            "\n"
            + "-" * 120
        )

        print(
            "REGIME:",
            regime
        )

        for row in grouped[
            regime
        ][
            :limit_per_regime
        ]:

            (
                accuracy,
                total,
                timeframe,
                regime_name,
                combination,
                window,
                bull_accuracy,
                bear_accuracy,
                avg_move,
            ) = row

            print(
                f"{timeframe:<7} | "
                f"{combination:<50} | "
                f"NEXT {window:<2} | "
                f"SAMPLES {total:<4} | "
                f"ACC {accuracy:6.2f}% | "
                f"BULL {bull_accuracy:6.2f}% | "
                f"BEAR {bear_accuracy:6.2f}% | "
                f"AVG MOVE {avg_move:.3f}%"
            )


def research_index(
    api,
    index_name
):
    print(
        "\n"
        + "#" * 120
    )

    print(
        "MARKET REGIME COMBINATION RESEARCH:",
        index_name
    )

    print(
        "MAX CANDLES:",
        MAX_CANDLES
    )

    index_results = defaultdict(
        create_stats
    )

    prepared_data = {}

    for timeframe in RESEARCH_TIMEFRAMES:

        timeframe_config = TIMEFRAMES[
            timeframe
        ]

        print(
            f"\nFETCHING {index_name} "
            f"{timeframe} "
            f"("
            f"{timeframe_config['api_interval']}"
            f")"
        )

        rows = fetch_max_950(
            api,
            CONFIG[
                index_name
            ][
                "segment"
            ],
            CONFIG[
                index_name
            ][
                "token"
            ],
            timeframe_config[
                "api_interval"
            ],
            timeframe_config[
                "chunk_days"
            ],
        )

        candles = prepare_candles(
            rows
        )

        if len(
            candles
        ) > MAX_CANDLES:

            candles = candles[
                -MAX_CANDLES:
            ]

        print(
            "CANDLES:",
            len(
                candles
            )
        )

        if not candles:
            continue

        states = build_indicator_states(
            candles
        )

        prepared_data[
            timeframe
        ] = (
            candles,
            states,
        )

        timeframe_results = (
            research_regime_single_timeframe(
                candles,
                states,
                timeframe
            )
        )

        merge_results(
            index_results,
            timeframe_results
        )

    if (
        "5M" in prepared_data
        and "15M" in prepared_data
    ):

        (
            candles_5m,
            states_5m,
        ) = prepared_data[
            "5M"
        ]

        (
            candles_15m,
            states_15m,
        ) = prepared_data[
            "15M"
        ]

        cross_results = (
            research_regime_cross_timeframe(
                candles_5m,
                states_5m,
                candles_15m,
                states_15m
            )
        )

        merge_results(
            index_results,
            cross_results
        )

    print_ranked_results(
        f"TOP REGIME COMBINATIONS: {index_name}",
        index_results,
        30
    )

    print_best_by_regime(
        f"BEST COMBINATIONS BY REGIME: {index_name}",
        index_results,
        10
    )

    return index_results
def load_api():
    api = MConnect(
        API_KEY
    )

    try:
        with open(
            TOKEN_FILE,
            "r"
        ) as file:
            access_token = (
                file.read().strip()
            )

        api.set_access_token(
            access_token
        )

    except Exception as error:
        print(
            "TOKEN ERROR:",
            error
        )
        raise

    return api


def main():
    api = load_api()

    combined_results = defaultdict(
        create_stats
    )

    index_results_map = {}

    for index_name in (
        "NIFTY",
        "SENSEX",
    ):

        try:
            results = research_index(
                api,
                index_name
            )

            index_results_map[
                index_name
            ] = results

            merge_results(
                combined_results,
                results
            )

        except Exception as error:
            print(
                "\nERROR",
                index_name,
                type(error).__name__,
                error
            )

            traceback.print_exc()

    print(
        "\n"
        + "=" * 120
    )

    print(
        "NIFTY + SENSEX COMBINED "
        "MARKET REGIME RESEARCH"
    )

    print_ranked_results(
        "FINAL TOP 30 REGIME COMBINATIONS: "
        "NIFTY + SENSEX COMBINED",
        combined_results,
        30
    )

    print_best_by_regime(
        "FINAL BEST COMBINATIONS BY REGIME: "
        "NIFTY + SENSEX COMBINED",
        combined_results,
        10
    )


if __name__ == "__main__":
    main()
