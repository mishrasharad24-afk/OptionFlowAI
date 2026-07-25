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

from historical.market_regime_combination_research import (
    detect_local_regime,
)


# ============================================================
# PRICE ACTION + REGIME + INDICATOR RESEARCH ENGINE
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
# DATA:
#   Maximum 950 candles per timeframe
#
# RESEARCH LAYERS:
#   1. Market Regime
#   2. Indicator Combination
#   3. Price Action Confirmation
#
# PRICE ACTION:
#   Bullish / Bearish Engulfing
#   Strong Bull / Bear Candle
#   Swing High Breakout
#   Swing Low Breakdown
#   Bullish / Bearish Rejection
#   Inside Bar Breakout
#   Market Structure HH-HL / LH-LL
#
# FUTURE OUTCOME:
#   Next 1 candle
#   Next 3 candles
#   Next 5 candles
#
# RESEARCH ONLY
# THIS SCRIPT DOES NOT PLACE TRADES
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


def candle_body(
    candle
):
    return abs(
        safe_float(
            candle["close"]
        )
        - safe_float(
            candle["open"]
        )
    )


def candle_range(
    candle
):
    return max(
        0.0,
        safe_float(
            candle["high"]
        )
        - safe_float(
            candle["low"]
        )
    )


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


def bullish_engulfing(
    candles,
    i
):
    if i < 1:
        return False

    previous = candles[
        i - 1
    ]

    current = candles[
        i
    ]

    previous_open = safe_float(
        previous["open"]
    )

    previous_close = safe_float(
        previous["close"]
    )

    current_open = safe_float(
        current["open"]
    )

    current_close = safe_float(
        current["close"]
    )

    return (
        previous_close
        < previous_open
        and current_close
        > current_open
        and current_open
        <= previous_close
        and current_close
        >= previous_open
    )


def bearish_engulfing(
    candles,
    i
):
    if i < 1:
        return False

    previous = candles[
        i - 1
    ]

    current = candles[
        i
    ]

    previous_open = safe_float(
        previous["open"]
    )

    previous_close = safe_float(
        previous["close"]
    )

    current_open = safe_float(
        current["open"]
    )

    current_close = safe_float(
        current["close"]
    )

    return (
        previous_close
        > previous_open
        and current_close
        < current_open
        and current_open
        >= previous_close
        and current_close
        <= previous_open
    )


def strong_candle_signal(
    candle
):
    total_range = candle_range(
        candle
    )

    if total_range <= 0:
        return None

    body = candle_body(
        candle
    )

    body_ratio = (
        body
        / total_range
    )

    if body_ratio < 0.65:
        return None

    direction = candle_direction(
        candle
    )

    if direction in (
        "BULLISH",
        "BEARISH",
    ):
        return direction

    return None


def rejection_signal(
    candle
):
    open_price = safe_float(
        candle["open"]
    )

    high = safe_float(
        candle["high"]
    )

    low = safe_float(
        candle["low"]
    )

    close_price = safe_float(
        candle["close"]
    )

    total_range = (
        high
        - low
    )

    if total_range <= 0:
        return None

    body_high = max(
        open_price,
        close_price
    )

    body_low = min(
        open_price,
        close_price
    )

    upper_wick = (
        high
        - body_high
    )

    lower_wick = (
        body_low
        - low
    )

    if (
        lower_wick
        >= total_range * 0.50
        and close_price > open_price
    ):
        return "BULLISH"

    if (
        upper_wick
        >= total_range * 0.50
        and close_price < open_price
    ):
        return "BEARISH"

    return None
def swing_breakout_signal(
    candles,
    i,
    lookback=5
):
    if i < lookback:
        return None

    current = candles[i]

    current_close = safe_float(
        current["close"]
    )

    previous_candles = candles[
        i - lookback:i
    ]

    previous_high = max(
        safe_float(
            candle["high"]
        )
        for candle in previous_candles
    )

    previous_low = min(
        safe_float(
            candle["low"]
        )
        for candle in previous_candles
    )

    if current_close > previous_high:
        return "BULLISH"

    if current_close < previous_low:
        return "BEARISH"

    return None


def inside_bar_breakout_signal(
    candles,
    i
):
    if i < 2:
        return None

    mother = candles[
        i - 2
    ]

    inside = candles[
        i - 1
    ]

    current = candles[
        i
    ]

    mother_high = safe_float(
        mother["high"]
    )

    mother_low = safe_float(
        mother["low"]
    )

    inside_high = safe_float(
        inside["high"]
    )

    inside_low = safe_float(
        inside["low"]
    )

    current_close = safe_float(
        current["close"]
    )

    is_inside = (
        inside_high
        < mother_high
        and inside_low
        > mother_low
    )

    if not is_inside:
        return None

    if current_close > mother_high:
        return "BULLISH"

    if current_close < mother_low:
        return "BEARISH"

    return None


def market_structure_signal(
    candles,
    i,
    lookback=6
):
    if i < lookback:
        return None

    half = (
        lookback // 2
    )

    older = candles[
        i - lookback:
        i - half
    ]

    newer = candles[
        i - half:
        i + 1
    ]

    if (
        not older
        or not newer
    ):
        return None

    older_high = max(
        safe_float(
            candle["high"]
        )
        for candle in older
    )

    older_low = min(
        safe_float(
            candle["low"]
        )
        for candle in older
    )

    newer_high = max(
        safe_float(
            candle["high"]
        )
        for candle in newer
    )

    newer_low = min(
        safe_float(
            candle["low"]
        )
        for candle in newer
    )

    if (
        newer_high > older_high
        and newer_low > older_low
    ):
        return "BULLISH"

    if (
        newer_high < older_high
        and newer_low < older_low
    ):
        return "BEARISH"

    return None


def build_price_action_states(
    candles
):
    states = []

    for i in range(
        len(candles)
    ):

        state = {}

        if bullish_engulfing(
            candles,
            i
        ):
            state[
                "ENGULFING"
            ] = "BULLISH"

        elif bearish_engulfing(
            candles,
            i
        ):
            state[
                "ENGULFING"
            ] = "BEARISH"

        else:
            state[
                "ENGULFING"
            ] = None

        state[
            "STRONG_CANDLE"
        ] = strong_candle_signal(
            candles[i]
        )

        state[
            "REJECTION"
        ] = rejection_signal(
            candles[i]
        )

        state[
            "SWING_BREAK"
        ] = swing_breakout_signal(
            candles,
            i
        )

        state[
            "INSIDE_BREAK"
        ] = inside_bar_breakout_signal(
            candles,
            i
        )

        state[
            "STRUCTURE"
        ] = market_structure_signal(
            candles,
            i
        )

        states.append(
            state
        )

    return states


def same_direction(
    *signals
):
    valid = [
        signal
        for signal in signals
        if signal in (
            "BULLISH",
            "BEARISH",
        )
    ]

    if not valid:
        return None

    if all(
        signal == "BULLISH"
        for signal in valid
    ):
        return "BULLISH"

    if all(
        signal == "BEARISH"
        for signal in valid
    ):
        return "BEARISH"

    return None


def get_price_action_combinations(
    indicator_combinations,
    price_action_state
):
    results = {}

    price_actions = {
        "ENGULFING":
            price_action_state[
                "ENGULFING"
            ],

        "STRONG_CANDLE":
            price_action_state[
                "STRONG_CANDLE"
            ],

        "REJECTION":
            price_action_state[
                "REJECTION"
            ],

        "SWING_BREAK":
            price_action_state[
                "SWING_BREAK"
            ],

        "INSIDE_BREAK":
            price_action_state[
                "INSIDE_BREAK"
            ],

        "STRUCTURE":
            price_action_state[
                "STRUCTURE"
            ],
    }

    for (
        indicator_name,
        indicator_signal
    ) in indicator_combinations.items():

        if indicator_signal not in (
            "BULLISH",
            "BEARISH",
        ):
            continue

        for (
            price_action_name,
            price_action_signal
        ) in price_actions.items():

            if price_action_signal not in (
                "BULLISH",
                "BEARISH",
            ):
                continue

            signal = same_direction(
                indicator_signal,
                price_action_signal
            )

            if signal is None:
                continue

            combination_name = (
                f"{indicator_name}"
                f"+PA_{price_action_name}"
            )

            results[
                combination_name
            ] = signal

    return results
def research_price_action_timeframe(
    candles,
    indicator_states,
    price_action_states,
    timeframe
):
    results = defaultdict(
        create_stats
    )

    signal_counts = defaultdict(
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

        indicator_combinations = (
            get_combinations(
                indicator_states[i]
            )
        )

        combinations = (
            get_price_action_combinations(
                indicator_combinations,
                price_action_states[i]
            )
        )

        for (
            combination,
            signal
        ) in combinations.items():

            if signal not in (
                "BULLISH",
                "BEARISH",
            ):
                continue

            signal_counts[
                (
                    regime,
                    combination,
                    signal,
                )
            ] += 1

            for window in FUTURE_WINDOWS:

                outcome = future_outcome(
                    candles,
                    i,
                    window
                )

                key = (
                    timeframe,
                    regime,
                    combination,
                    window,
                )

                update_stats(
                    results[key],
                    signal,
                    outcome
                )

    print(
        f"\nPRICE ACTION SIGNALS: "
        f"{timeframe}"
    )

    print(
        "TOTAL QUALIFIED SETUPS:",
        sum(
            signal_counts.values()
        )
    )

    return results


def research_price_action_cross_timeframe(
    candles_5m,
    states_5m,
    price_action_5m,
    candles_15m,
    states_15m
):
    results = defaultdict(
        create_stats
    )

    state_map_15m = (
        build_15m_state_map(
            candles_15m,
            states_15m
        )
    )

    matched = 0
    qualified = 0

    for i in range(
        len(candles_5m)
    ):

        state_15m = (
            get_15m_state_for_5m(
                candles_5m[i],
                state_map_15m
            )
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

        indicator_combinations = (
            cross_timeframe_combinations(
                states_5m[i],
                state_15m
            )
        )

        combinations = (
            get_price_action_combinations(
                indicator_combinations,
                price_action_5m[i]
            )
        )

        for (
            combination,
            signal
        ) in combinations.items():

            if signal not in (
                "BULLISH",
                "BEARISH",
            ):
                continue

            qualified += 1

            for window in FUTURE_WINDOWS:

                outcome = future_outcome(
                    candles_5m,
                    i,
                    window
                )

                key = (
                    "5M+15M",
                    regime,
                    combination,
                    window,
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
        "5M + 15M QUALIFIED PA SETUPS:",
        qualified
    )

    return results


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

    bull_accuracy = 0.0

    if bullish > 0:
        bull_accuracy = (
            stats[
                "bull_correct"
            ]
            / bullish
        ) * 100.0

    bear_accuracy = 0.0

    if bearish > 0:
        bear_accuracy = (
            stats[
                "bear_correct"
            ]
            / bearish
        ) * 100.0

    avg_move = (
        stats[
            "move_sum"
        ]
        / total
    )

    return {
        "accuracy": accuracy,
        "total": total,
        "bull_accuracy":
            bull_accuracy,
        "bear_accuracy":
            bear_accuracy,
        "avg_move":
            avg_move,
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
                metrics["accuracy"],
                metrics["total"],
                timeframe,
                regime,
                combination,
                window,
                metrics["bull_accuracy"],
                metrics["bear_accuracy"],
                metrics["avg_move"],
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
            f"{combination:<55} | "
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
                f"{combination:<55} | "
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
        "PRICE ACTION + REGIME RESEARCH:",
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
            CONFIG[index_name][
                "segment"
            ],
            CONFIG[index_name][
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

        indicator_states = (
            build_indicator_states(
                candles
            )
        )

        price_action_states = (
            build_price_action_states(
                candles
            )
        )

        prepared_data[
            timeframe
        ] = (
            candles,
            indicator_states,
            price_action_states,
        )

        timeframe_results = (
            research_price_action_timeframe(
                candles,
                indicator_states,
                price_action_states,
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
            price_action_5m,
        ) = prepared_data[
            "5M"
        ]

        (
            candles_15m,
            states_15m,
            price_action_15m,
        ) = prepared_data[
            "15M"
        ]

        cross_results = (
            research_price_action_cross_timeframe(
                candles_5m,
                states_5m,
                price_action_5m,
                candles_15m,
                states_15m
            )
        )

        merge_results(
            index_results,
            cross_results
        )

    print_ranked_results(
        f"TOP PRICE ACTION SETUPS: {index_name}",
        index_results,
        30
    )

    print_best_by_regime(
        f"BEST PRICE ACTION SETUPS BY REGIME: {index_name}",
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

    for index_name in (
        "NIFTY",
        "SENSEX",
    ):

        try:
            results = research_index(
                api,
                index_name
            )

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
        "PRICE ACTION + REGIME RESEARCH"
    )

    print_ranked_results(
        "FINAL TOP 30 PRICE ACTION SETUPS: "
        "NIFTY + SENSEX COMBINED",
        combined_results,
        30
    )

    print_best_by_regime(
        "FINAL BEST PRICE ACTION SETUPS BY REGIME: "
        "NIFTY + SENSEX COMBINED",
        combined_results,
        10
    )


if __name__ == "__main__":
    main()
