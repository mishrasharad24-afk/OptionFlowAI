import sys
import os
import traceback
from collections import defaultdict
from datetime import datetime

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


# ============================================================
# CLEAN INDICATOR COMBINATION RESEARCH ENGINE
#
# INDEX:
#   NIFTY
#   SENSEX
#
# TIMEFRAMES:
#   5M
#   15M
#
# MAX DATA:
#   950 candles per timeframe
#
# PURPOSE:
#   Research individual indicator combinations
#   Research 5M + 15M confirmation combinations
#   Measure Next 1 / 3 / 5 candle directional accuracy
#
# IMPORTANT:
#   Research only.
#   No live orders.
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


def prepare_candles(
    rows
):
    candles = []

    for row in rows:

        if len(row) < 6:
            continue

        candles.append(
            {
                "time": row[0],
                "open": safe_float(
                    row[1]
                ),
                "high": safe_float(
                    row[2]
                ),
                "low": safe_float(
                    row[3]
                ),
                "close": safe_float(
                    row[4]
                ),
                "volume": safe_float(
                    row[5]
                ),
            }
        )

    return candles


def create_stats():
    return {
        "total": 0,
        "correct": 0,
        "bullish": 0,
        "bearish": 0,
        "bull_correct": 0,
        "bear_correct": 0,
        "move_sum": 0.0,
    }


def ema(
    values,
    period
):
    if not values:
        return []

    multiplier = (
        2.0
        / (
            period + 1
        )
    )

    result = [
        values[0]
    ]

    for value in values[1:]:

        previous = result[-1]

        current = (
            value
            * multiplier
            + previous
            * (
                1.0
                - multiplier
            )
        )

        result.append(
            current
        )

    return result


def sma(
    values,
    period
):
    result = [
        None
    ] * len(values)

    if period <= 0:
        return result

    running_sum = 0.0

    for i, value in enumerate(
        values
    ):

        running_sum += value

        if i >= period:
            running_sum -= (
                values[
                    i - period
                ]
            )

        if i >= (
            period - 1
        ):
            result[i] = (
                running_sum
                / period
            )

    return result


def future_outcome(
    candles,
    index,
    window
):
    future_index = (
        index + window
    )

    if future_index >= len(
        candles
    ):
        return None

    current_close = safe_float(
        candles[index][
            "close"
        ]
    )

    future_close = safe_float(
        candles[future_index][
            "close"
        ]
    )

    if current_close <= 0:
        return None

    move_pct = (
        (
            future_close
            - current_close
        )
        / current_close
    ) * 100.0

    if future_close > current_close:
        direction = "BULLISH"

    elif future_close < current_close:
        direction = "BEARISH"

    else:
        direction = "FLAT"

    return {
        "direction": direction,
        "move_pct": abs(
            move_pct
        ),
    }


def update_stats(
    stats,
    signal,
    outcome
):
    if signal not in (
        "BULLISH",
        "BEARISH",
    ):
        return

    if outcome is None:
        return

    actual = outcome[
        "direction"
    ]

    if actual == "FLAT":
        return

    stats[
        "total"
    ] += 1

    stats[
        "move_sum"
    ] += outcome[
        "move_pct"
    ]

    if signal == "BULLISH":

        stats[
            "bullish"
        ] += 1

        if actual == "BULLISH":

            stats[
                "correct"
            ] += 1

            stats[
                "bull_correct"
            ] += 1

    elif signal == "BEARISH":

        stats[
            "bearish"
        ] += 1

        if actual == "BEARISH":

            stats[
                "correct"
            ] += 1

            stats[
                "bear_correct"
            ] += 1
def calculate_rsi(
    closes,
    period=14
):
    result = [
        None
    ] * len(closes)

    if len(closes) <= period:
        return result

    gains = []
    losses = []

    for i in range(
        1,
        len(closes)
    ):

        change = (
            closes[i]
            - closes[i - 1]
        )

        gains.append(
            max(
                change,
                0.0
            )
        )

        losses.append(
            max(
                -change,
                0.0
            )
        )

    for i in range(
        period,
        len(closes)
    ):

        start = (
            i - period
        )

        avg_gain = (
            sum(
                gains[
                    start:i
                ]
            )
            / period
        )

        avg_loss = (
            sum(
                losses[
                    start:i
                ]
            )
            / period
        )

        if avg_loss == 0:

            if avg_gain > 0:
                result[i] = 100.0
            else:
                result[i] = 50.0

        else:

            rs = (
                avg_gain
                / avg_loss
            )

            result[i] = (
                100.0
                - (
                    100.0
                    / (
                        1.0 + rs
                    )
                )
            )

    return result


def calculate_atr(
    candles,
    period=14
):
    true_ranges = []

    for i in range(
        len(candles)
    ):

        high = candles[i][
            "high"
        ]

        low = candles[i][
            "low"
        ]

        if i == 0:

            tr = (
                high
                - low
            )

        else:

            previous_close = (
                candles[
                    i - 1
                ][
                    "close"
                ]
            )

            tr = max(
                high - low,
                abs(
                    high
                    - previous_close
                ),
                abs(
                    low
                    - previous_close
                ),
            )

        true_ranges.append(
            tr
        )

    return sma(
        true_ranges,
        period
    )


def calculate_stochastic(
    candles,
    period=14
):
    result = [
        None
    ] * len(candles)

    for i in range(
        len(candles)
    ):

        if i < (
            period - 1
        ):
            continue

        start = (
            i - period + 1
        )

        highest = max(
            candle[
                "high"
            ]
            for candle in candles[
                start:i + 1
            ]
        )

        lowest = min(
            candle[
                "low"
            ]
            for candle in candles[
                start:i + 1
            ]
        )

        close = candles[i][
            "close"
        ]

        price_range = (
            highest
            - lowest
        )

        if price_range <= 0:
            result[i] = 50.0

        else:

            result[i] = (
                (
                    close
                    - lowest
                )
                / price_range
            ) * 100.0

    return result


def build_indicator_states(
    candles
):
    closes = [
        candle[
            "close"
        ]
        for candle in candles
    ]

    volumes = [
        candle[
            "volume"
        ]
        for candle in candles
    ]

    ema9 = ema(
        closes,
        9
    )

    ema20 = ema(
        closes,
        20
    )

    ema50 = ema(
        closes,
        50
    )

    rsi14 = calculate_rsi(
        closes,
        14
    )

    atr14 = calculate_atr(
        candles,
        14
    )

    stochastic = (
        calculate_stochastic(
            candles,
            14
        )
    )

    volume_sma20 = sma(
        volumes,
        20
    )

    states = []

    for i in range(
        len(candles)
    ):

        state = {}

        # --------------------------------
        # EMA TREND
        # --------------------------------

        if (
            ema9[i]
            > ema20[i]
            > ema50[i]
        ):

            state[
                "EMA"
            ] = "BULLISH"

        elif (
            ema9[i]
            < ema20[i]
            < ema50[i]
        ):

            state[
                "EMA"
            ] = "BEARISH"

        else:

            state[
                "EMA"
            ] = "NEUTRAL"

        # --------------------------------
        # RSI
        # --------------------------------

        if rsi14[i] is None:

            state[
                "RSI"
            ] = "NEUTRAL"

        elif rsi14[i] >= 55:

            state[
                "RSI"
            ] = "BULLISH"

        elif rsi14[i] <= 45:

            state[
                "RSI"
            ] = "BEARISH"

        else:

            state[
                "RSI"
            ] = "NEUTRAL"

        # --------------------------------
        # MOMENTUM
        # --------------------------------

        if i < 5:

            state[
                "MOMENTUM"
            ] = "NEUTRAL"

        else:

            old_close = closes[
                i - 5
            ]

            if closes[i] > old_close:

                state[
                    "MOMENTUM"
                ] = "BULLISH"

            elif closes[i] < old_close:

                state[
                    "MOMENTUM"
                ] = "BEARISH"

            else:

                state[
                    "MOMENTUM"
                ] = "NEUTRAL"

        # --------------------------------
        # ATR EXPANSION + DIRECTION
        # --------------------------------

        if (
            i < 1
            or atr14[i] is None
            or atr14[i - 1] is None
        ):

            state[
                "ATR"
            ] = "NEUTRAL"

        elif atr14[i] > atr14[i - 1]:

            if closes[i] > closes[i - 1]:

                state[
                    "ATR"
                ] = "BULLISH"

            elif closes[i] < closes[i - 1]:

                state[
                    "ATR"
                ] = "BEARISH"

            else:

                state[
                    "ATR"
                ] = "NEUTRAL"

        else:

            state[
                "ATR"
            ] = "NEUTRAL"

        # --------------------------------
        # STOCHASTIC
        # --------------------------------

        if stochastic[i] is None:

            state[
                "STOCHASTIC"
            ] = "NEUTRAL"

        elif stochastic[i] >= 60:

            state[
                "STOCHASTIC"
            ] = "BULLISH"

        elif stochastic[i] <= 40:

            state[
                "STOCHASTIC"
            ] = "BEARISH"

        else:

            state[
                "STOCHASTIC"
            ] = "NEUTRAL"

        # --------------------------------
        # VOLUME SPIKE + DIRECTION
        # --------------------------------

        if (
            volume_sma20[i] is None
            or volume_sma20[i] <= 0
        ):

            state[
                "VOLUME"
            ] = "NEUTRAL"

        elif volumes[i] >= (
            volume_sma20[i]
            * 1.5
        ):

            if (
                candles[i][
                    "close"
                ]
                > candles[i][
                    "open"
                ]
            ):

                state[
                    "VOLUME"
                ] = "BULLISH"

            elif (
                candles[i][
                    "close"
                ]
                < candles[i][
                    "open"
                ]
            ):

                state[
                    "VOLUME"
                ] = "BEARISH"

            else:

                state[
                    "VOLUME"
                ] = "NEUTRAL"

        else:

            state[
                "VOLUME"
            ] = "NEUTRAL"

        states.append(
            state
        )

    return states
def same_direction(
    *values
):
    valid = [
        value
        for value in values
        if value in (
            "BULLISH",
            "BEARISH",
        )
    ]

    if len(valid) != len(values):
        return None

    if all(
        value == "BULLISH"
        for value in valid
    ):
        return "BULLISH"

    if all(
        value == "BEARISH"
        for value in valid
    ):
        return "BEARISH"

    return None


def get_combinations(
    state
):
    combinations = {}

    combinations[
        "EMA+RSI"
    ] = same_direction(
        state["EMA"],
        state["RSI"],
    )

    combinations[
        "EMA+MOMENTUM"
    ] = same_direction(
        state["EMA"],
        state["MOMENTUM"],
    )

    combinations[
        "RSI+MOMENTUM"
    ] = same_direction(
        state["RSI"],
        state["MOMENTUM"],
    )

    combinations[
        "EMA+ATR"
    ] = same_direction(
        state["EMA"],
        state["ATR"],
    )

    combinations[
        "RSI+ATR"
    ] = same_direction(
        state["RSI"],
        state["ATR"],
    )

    combinations[
        "MOMENTUM+ATR"
    ] = same_direction(
        state["MOMENTUM"],
        state["ATR"],
    )

    combinations[
        "EMA+STOCHASTIC"
    ] = same_direction(
        state["EMA"],
        state["STOCHASTIC"],
    )

    combinations[
        "RSI+STOCHASTIC"
    ] = same_direction(
        state["RSI"],
        state["STOCHASTIC"],
    )

    combinations[
        "EMA+VOLUME"
    ] = same_direction(
        state["EMA"],
        state["VOLUME"],
    )

    combinations[
        "MOMENTUM+VOLUME"
    ] = same_direction(
        state["MOMENTUM"],
        state["VOLUME"],
    )

    combinations[
        "EMA+RSI+MOMENTUM"
    ] = same_direction(
        state["EMA"],
        state["RSI"],
        state["MOMENTUM"],
    )

    combinations[
        "EMA+RSI+ATR"
    ] = same_direction(
        state["EMA"],
        state["RSI"],
        state["ATR"],
    )

    combinations[
        "EMA+MOMENTUM+ATR"
    ] = same_direction(
        state["EMA"],
        state["MOMENTUM"],
        state["ATR"],
    )

    combinations[
        "RSI+MOMENTUM+ATR"
    ] = same_direction(
        state["RSI"],
        state["MOMENTUM"],
        state["ATR"],
    )

    combinations[
        "EMA+RSI+STOCHASTIC"
    ] = same_direction(
        state["EMA"],
        state["RSI"],
        state["STOCHASTIC"],
    )

    combinations[
        "EMA+RSI+VOLUME"
    ] = same_direction(
        state["EMA"],
        state["RSI"],
        state["VOLUME"],
    )

    combinations[
        "EMA+MOMENTUM+VOLUME"
    ] = same_direction(
        state["EMA"],
        state["MOMENTUM"],
        state["VOLUME"],
    )

    combinations[
        "EMA+RSI+MOMENTUM+ATR"
    ] = same_direction(
        state["EMA"],
        state["RSI"],
        state["MOMENTUM"],
        state["ATR"],
    )

    combinations[
        "ALL_6"
    ] = same_direction(
        state["EMA"],
        state["RSI"],
        state["MOMENTUM"],
        state["ATR"],
        state["STOCHASTIC"],
        state["VOLUME"],
    )

    return combinations


def future_outcome(
    candles,
    index,
    window
):
    future_index = (
        index + window
    )

    if future_index >= len(candles):
        return None

    current_close = candles[
        index
    ][
        "close"
    ]

    future_close = candles[
        future_index
    ][
        "close"
    ]

    if current_close <= 0:
        return None

    move_pct = (
        (
            future_close
            - current_close
        )
        / current_close
    ) * 100.0

    if future_close > current_close:
        direction = "BULLISH"

    elif future_close < current_close:
        direction = "BEARISH"

    else:
        direction = "FLAT"

    return {
        "direction": direction,
        "move_pct": abs(
            move_pct
        ),
    }


def update_stats(
    stats,
    signal,
    outcome
):
    if signal not in (
        "BULLISH",
        "BEARISH",
    ):
        return

    if outcome is None:
        return

    actual = outcome[
        "direction"
    ]

    if actual == "FLAT":
        return

    stats[
        "total"
    ] += 1

    stats[
        "move_sum"
    ] += outcome[
        "move_pct"
    ]

    if signal == "BULLISH":

        stats[
            "bullish"
        ] += 1

        if actual == "BULLISH":

            stats[
                "correct"
            ] += 1

            stats[
                "bull_correct"
            ] += 1

    elif signal == "BEARISH":

        stats[
            "bearish"
        ] += 1

        if actual == "BEARISH":

            stats[
                "correct"
            ] += 1

            stats[
                "bear_correct"
            ] += 1


def research_single_timeframe(
    candles,
    states,
    timeframe
):
    results = defaultdict(
        create_stats
    )

    for i in range(
        len(candles)
    ):

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

                key = (
                    timeframe,
                    combination,
                    window,
                )

                update_stats(
                    results[key],
                    signal,
                    outcome
                )

    return results
def normalize_to_15m(
    timestamp
):
    try:
        timestamp = str(
            timestamp
        )

        date_part = timestamp[
            :10
        ]

        time_part = timestamp[
            11:16
        ]

        hour = int(
            time_part[:2]
        )

        minute = int(
            time_part[3:5]
        )

        aligned_minute = (
            minute // 15
        ) * 15

        return (
            f"{date_part} "
            f"{hour:02d}:"
            f"{aligned_minute:02d}"
        )

    except Exception:
        return None


def build_15m_state_map(
    candles_15m,
    states_15m
):
    state_map = {}

    for i in range(
        min(
            len(candles_15m),
            len(states_15m)
        )
    ):

        timestamp = candles_15m[
            i
        ][
            "time"
        ]

        key = normalize_to_15m(
            timestamp
        )

        if key is not None:

            state_map[
                key
            ] = states_15m[
                i
            ]

    return state_map


def get_15m_state_for_5m(
    candle_5m,
    state_map_15m
):
    timestamp = candle_5m[
        "time"
    ]

    key = normalize_to_15m(
        timestamp
    )

    if key is None:
        return None

    return state_map_15m.get(
        key
    )


def cross_timeframe_combinations(
    state_5m,
    state_15m
):
    combinations = {}

    combinations[
        "15M_EMA+5M_EMA"
    ] = same_direction(
        state_15m["EMA"],
        state_5m["EMA"],
    )

    combinations[
        "15M_EMA+5M_RSI"
    ] = same_direction(
        state_15m["EMA"],
        state_5m["RSI"],
    )

    combinations[
        "15M_EMA+5M_MOMENTUM"
    ] = same_direction(
        state_15m["EMA"],
        state_5m["MOMENTUM"],
    )

    combinations[
        "15M_RSI+5M_EMA"
    ] = same_direction(
        state_15m["RSI"],
        state_5m["EMA"],
    )

    combinations[
        "15M_RSI+5M_RSI"
    ] = same_direction(
        state_15m["RSI"],
        state_5m["RSI"],
    )

    combinations[
        "15M_MOMENTUM+5M_MOMENTUM"
    ] = same_direction(
        state_15m["MOMENTUM"],
        state_5m["MOMENTUM"],
    )

    combinations[
        "15M_EMA+5M_EMA+RSI"
    ] = same_direction(
        state_15m["EMA"],
        state_5m["EMA"],
        state_5m["RSI"],
    )

    combinations[
        "15M_EMA+5M_EMA+MOMENTUM"
    ] = same_direction(
        state_15m["EMA"],
        state_5m["EMA"],
        state_5m["MOMENTUM"],
    )

    combinations[
        "15M_EMA+5M_RSI+MOMENTUM"
    ] = same_direction(
        state_15m["EMA"],
        state_5m["RSI"],
        state_5m["MOMENTUM"],
    )

    combinations[
        "15M_RSI+5M_EMA+MOMENTUM"
    ] = same_direction(
        state_15m["RSI"],
        state_5m["EMA"],
        state_5m["MOMENTUM"],
    )

    combinations[
        "15M_EMA+RSI+5M_EMA+RSI"
    ] = same_direction(
        state_15m["EMA"],
        state_15m["RSI"],
        state_5m["EMA"],
        state_5m["RSI"],
    )

    combinations[
        "15M_EMA+MOMENTUM+5M_EMA+MOMENTUM"
    ] = same_direction(
        state_15m["EMA"],
        state_15m["MOMENTUM"],
        state_5m["EMA"],
        state_5m["MOMENTUM"],
    )

    combinations[
        "15M_EMA+RSI+MOMENTUM+5M_EMA+RSI+MOMENTUM"
    ] = same_direction(
        state_15m["EMA"],
        state_15m["RSI"],
        state_15m["MOMENTUM"],
        state_5m["EMA"],
        state_5m["RSI"],
        state_5m["MOMENTUM"],
    )

    return combinations


def research_cross_timeframe(
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

                key = (
                    "5M+15M",
                    combination,
                    window,
                )

                update_stats(
                    results[key],
                    signal,
                    outcome
                )

    print(
        "5M + 15M MATCHED CANDLES:",
        matched
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


def calculate_result_metrics(
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


def print_ranked_results(
    title,
    results,
    limit=20
):
    print(
        "=" * 100
    )

    print(
        title
    )

    ranked = []

    for key, stats in results.items():

        metrics = (
            calculate_result_metrics(
                stats
            )
        )

        if metrics is None:
            continue

        if metrics[
            "total"
        ] < MIN_SAMPLE_SIZE:
            continue

        timeframe = key[
            0
        ]

        combination = key[
            1
        ]

        window = key[
            2
        ]

        ranked.append(
            (
                metrics[
                    "accuracy"
                ],
                metrics[
                    "total"
                ],
                timeframe,
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
        key=lambda x: (
            x[0],
            x[1],
        ),
        reverse=True
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

    return ranked


def research_index(
    api,
    index_name
):
    print(
        "\n"
        + "#" * 100
    )

    print(
        "5M + 15M COMBINATION RESEARCH:",
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
            f"FETCHING {index_name} "
            f"{timeframe} "
            f"("
            f"{timeframe_config['api_interval']}"
            f")"
        )

        rows = fetch_max_950(
    api,
    CONFIG[index_name]["segment"],
    CONFIG[index_name]["token"],
    timeframe_config["api_interval"],
    timeframe_config["chunk_days"],
)
        candles = prepare_candles(
            rows
        )

        if len(candles) > MAX_CANDLES:

            candles = candles[
                -MAX_CANDLES:
            ]

        print(
            "CANDLES:",
            len(candles)
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

        single_results = (
            research_single_timeframe(
                candles,
                states,
                timeframe
            )
        )

        merge_results(
            index_results,
            single_results
        )

    if (
        "5M" in prepared_data
        and "15M" in prepared_data
    ):

        candles_5m, states_5m = (
            prepared_data[
                "5M"
            ]
        )

        candles_15m, states_15m = (
            prepared_data[
                "15M"
            ]
        )

        cross_results = (
            research_cross_timeframe(
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
        f"TOP 20 COMBINATIONS: {index_name}",
        index_results,
        20
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

    all_index_results = {}

    for index_name in (
        "NIFTY",
        "SENSEX",
    ):

        try:

            results = research_index(
                api,
                index_name
            )

            all_index_results[
                index_name
            ] = results

            merge_results(
                combined_results,
                results
            )

        except Exception as error:

            print(
                "ERROR",
                index_name,
                type(error).__name__,
                error
            )

            traceback.print_exc()

    print(
        "\n"
        + "=" * 100
    )

    print(
        "NIFTY + SENSEX COMBINED "
        "COMBINATION RESEARCH"
    )

    print_ranked_results(
        "FINAL TOP 20: "
        "NIFTY + SENSEX COMBINED",
        combined_results,
        20
    )


if __name__ == "__main__":
    main()
