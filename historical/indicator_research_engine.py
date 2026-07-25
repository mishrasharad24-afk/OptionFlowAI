import sys
import os
import math
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


# ============================================================
# CONSOLIDATED INDICATOR RESEARCH ENGINE
#
# INDEX:
#   NIFTY
#   SENSEX
#
# DATA:
#   Maximum 950 candles per timeframe
#
# TIMEFRAMES:
#   1M
#   5M
#   15M
#   60M
#   DAY
#
# RESEARCH INDICATORS:
#   EMA 9
#   EMA 20
#   EMA 50
#   RSI 14
#   ATR 14
#   VWAP
#   SUPERTREND
#   STOCHASTIC
#   VOLUME SPIKE
#   MOMENTUM
#
# FUTURE OUTCOME:
#   Next 1 candle
#   Next 3 candles
#   Next 5 candles
#
# IMPORTANT:
#   This engine researches indicators.
#   It does NOT place trades.
# ============================================================


MIN_SAMPLE_SIZE = 20

FUTURE_WINDOWS = [
    1,
    3,
    5,
]


INDICATOR_TIMEFRAMES = {

    "1M": [
        "EMA",
        "VWAP",
        "RSI",
        "ATR",
        "STOCHASTIC",
        "VOLUME_SPIKE",
        "MOMENTUM",
    ],

    "5M": [
        "EMA",
        "VWAP",
        "RSI",
        "ATR",
        "SUPERTREND",
        "STOCHASTIC",
        "VOLUME_SPIKE",
        "MOMENTUM",
    ],

    "15M": [
        "EMA",
        "VWAP",
        "RSI",
        "ATR",
        "SUPERTREND",
        "STOCHASTIC",
        "VOLUME_SPIKE",
        "MOMENTUM",
    ],

    "60M": [
        "EMA",
        "RSI",
        "ATR",
        "SUPERTREND",
        "MOMENTUM",
    ],

    "DAY": [
        "EMA",
        "RSI",
        "ATR",
        "SUPERTREND",
        "MOMENTUM",
    ],
}


def safe_float(
    value,
    default=0.0
):

    try:

        return float(
            value
        )

    except Exception:

        return default


def prepare_candles(
    rows
):

    candles = []

    for row in rows:

        if len(row) < 6:
            continue

        candles.append({

            "time":
                row[0],

            "open":
                safe_float(
                    row[1]
                ),

            "high":
                safe_float(
                    row[2]
                ),

            "low":
                safe_float(
                    row[3]
                ),

            "close":
                safe_float(
                    row[4]
                ),

            "volume":
                safe_float(
                    row[5]
                ),

        })

    return candles


def sma(
    values,
    period
):

    result = [
        None
    ] * len(
        values
    )

    if period <= 0:

        return result

    if len(values) < period:

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


def ema(
    values,
    period
):

    result = [
        None
    ] * len(
        values
    )

    if (
        period <= 0
        or len(values) < period
    ):

        return result

    seed = sum(
        values[
            :period
        ]
    ) / period

    result[
        period - 1
    ] = seed

    multiplier = (
        2.0
        / (
            period + 1
        )
    )

    previous = seed

    for i in range(
        period,
        len(values)
    ):

        current = (
            (
                values[i]
                - previous
            )
            * multiplier
            + previous
        )

        result[i] = current

        previous = current

    return result


def calculate_rsi(
    closes,
    period=14
):

    result = [
        None
    ] * len(
        closes
    )

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
                0
            )
        )

        losses.append(
            max(
                -change,
                0
            )
        )

    avg_gain = (
        sum(
            gains[
                :period
            ]
        )
        / period
    )

    avg_loss = (
        sum(
            losses[
                :period
            ]
        )
        / period
    )

    if avg_loss == 0:

        result[
            period
        ] = 100.0

    else:

        rs = (
            avg_gain
            / avg_loss
        )

        result[
            period
        ] = (
            100
            - (
                100
                / (
                    1 + rs
                )
            )
        )

    for i in range(
        period + 1,
        len(closes)
    ):

        gain = gains[
            i - 1
        ]

        loss = losses[
            i - 1
        ]

        avg_gain = (
            (
                avg_gain
                * (
                    period - 1
                )
            )
            + gain
        ) / period

        avg_loss = (
            (
                avg_loss
                * (
                    period - 1
                )
            )
            + loss
        ) / period

        if avg_loss == 0:

            result[i] = (
                100.0
            )

        else:

            rs = (
                avg_gain
                / avg_loss
            )

            result[i] = (
                100
                - (
                    100
                    / (
                        1 + rs
                    )
                )
            )

    return result


def calculate_atr(
    highs,
    lows,
    closes,
    period=14
):

    true_ranges = []

    for i in range(
        len(closes)
    ):

        if i == 0:

            tr = (
                highs[i]
                - lows[i]
            )

        else:

            tr = max(

                highs[i]
                - lows[i],

                abs(
                    highs[i]
                    - closes[i - 1]
                ),

                abs(
                    lows[i]
                    - closes[i - 1]
                ),

            )

        true_ranges.append(
            tr
        )

    return ema(
        true_ranges,
        period
    )
def calculate_vwap(
    candles
):

    result = [
        None
    ] * len(
        candles
    )

    cumulative_pv = 0.0
    cumulative_volume = 0.0
    current_day = None

    for i, candle in enumerate(
        candles
    ):

        candle_day = (
            candle["time"][:10]
        )

        if (
            current_day
            != candle_day
        ):

            current_day = (
                candle_day
            )

            cumulative_pv = 0.0
            cumulative_volume = 0.0

        typical_price = (
            candle["high"]
            + candle["low"]
            + candle["close"]
        ) / 3.0

        volume = (
            candle["volume"]
        )

        cumulative_pv += (
            typical_price
            * volume
        )

        cumulative_volume += (
            volume
        )

        if cumulative_volume > 0:

            result[i] = (
                cumulative_pv
                / cumulative_volume
            )

    return result


def calculate_stochastic(
    highs,
    lows,
    closes,
    period=14
):

    result = [
        None
    ] * len(
        closes
    )

    for i in range(
        period - 1,
        len(closes)
    ):

        highest = max(
            highs[
                i - period + 1:
                i + 1
            ]
        )

        lowest = min(
            lows[
                i - period + 1:
                i + 1
            ]
        )

        price_range = (
            highest
            - lowest
        )

        if price_range == 0:

            result[i] = 50.0

        else:

            result[i] = (
                (
                    closes[i]
                    - lowest
                )
                / price_range
            ) * 100.0

    return result


def calculate_supertrend(
    highs,
    lows,
    closes,
    atr_values,
    multiplier=3.0
):

    size = len(
        closes
    )

    result = [
        None
    ] * size

    upper_band = [
        None
    ] * size

    lower_band = [
        None
    ] * size

    direction = [
        None
    ] * size

    for i in range(
        size
    ):

        atr_value = (
            atr_values[i]
        )

        if atr_value is None:
            continue

        hl2 = (
            highs[i]
            + lows[i]
        ) / 2.0

        basic_upper = (
            hl2
            + multiplier
            * atr_value
        )

        basic_lower = (
            hl2
            - multiplier
            * atr_value
        )

        if (
            i == 0
            or upper_band[
                i - 1
            ] is None
        ):

            upper_band[i] = (
                basic_upper
            )

            lower_band[i] = (
                basic_lower
            )

        else:

            if (
                basic_upper
                < upper_band[
                    i - 1
                ]
                or closes[
                    i - 1
                ]
                > upper_band[
                    i - 1
                ]
            ):

                upper_band[i] = (
                    basic_upper
                )

            else:

                upper_band[i] = (
                    upper_band[
                        i - 1
                    ]
                )

            if (
                basic_lower
                > lower_band[
                    i - 1
                ]
                or closes[
                    i - 1
                ]
                < lower_band[
                    i - 1
                ]
            ):

                lower_band[i] = (
                    basic_lower
                )

            else:

                lower_band[i] = (
                    lower_band[
                        i - 1
                    ]
                )

        if (
            i == 0
            or direction[
                i - 1
            ] is None
        ):

            if closes[i] >= hl2:

                direction[i] = 1

            else:

                direction[i] = -1

        elif (
            direction[
                i - 1
            ] == 1
        ):

            if (
                closes[i]
                < lower_band[i]
            ):

                direction[i] = -1

            else:

                direction[i] = 1

        else:

            if (
                closes[i]
                > upper_band[i]
            ):

                direction[i] = 1

            else:

                direction[i] = -1

        if direction[i] == 1:

            result[i] = (
                lower_band[i]
            )

        else:

            result[i] = (
                upper_band[i]
            )

    return (
        result,
        direction
    )


def calculate_volume_spike(
    volumes,
    period=20,
    multiplier=1.5
):

    result = [
        None
    ] * len(
        volumes
    )

    average_volume = sma(
        volumes,
        period
    )

    for i in range(
        len(volumes)
    ):

        avg = (
            average_volume[i]
        )

        if (
            avg is None
            or avg <= 0
        ):

            continue

        ratio = (
            volumes[i]
            / avg
        )

        if ratio >= multiplier:

            result[i] = (
                "SPIKE"
            )

        else:

            result[i] = (
                "NORMAL"
            )

    return result


def calculate_momentum(
    closes,
    period=5
):

    result = [
        None
    ] * len(
        closes
    )

    for i in range(
        period,
        len(closes)
    ):

        previous = (
            closes[
                i - period
            ]
        )

        if previous == 0:
            continue

        result[i] = (
            (
                closes[i]
                - previous
            )
            / previous
        ) * 100.0

    return result


def build_indicator_data(
    candles
):

    closes = [
        x["close"]
        for x in candles
    ]

    highs = [
        x["high"]
        for x in candles
    ]

    lows = [
        x["low"]
        for x in candles
    ]

    volumes = [
        x["volume"]
        for x in candles
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
        highs,
        lows,
        closes,
        14
    )

    vwap = calculate_vwap(
        candles
    )

    stochastic = (
        calculate_stochastic(
            highs,
            lows,
            closes,
            14
        )
    )

    supertrend, st_direction = (
        calculate_supertrend(
            highs,
            lows,
            closes,
            atr14,
            3.0
        )
    )

    volume_spike = (
        calculate_volume_spike(
            volumes,
            20,
            1.5
        )
    )

    momentum = (
        calculate_momentum(
            closes,
            5
        )
    )

    return {
        "ema9": ema9,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi14,
        "atr": atr14,
        "vwap": vwap,
        "stochastic": stochastic,
        "supertrend": supertrend,
        "st_direction": st_direction,
        "volume_spike": volume_spike,
        "momentum": momentum,
    }
def get_indicator_signals(
    candles,
    data,
    i,
    timeframe
):

    signals = {}

    close = candles[i][
        "close"
    ]

    allowed = (
        INDICATOR_TIMEFRAMES[
            timeframe
        ]
    )

    # ========================================================
    # EMA ALIGNMENT
    # ========================================================

    if "EMA" in allowed:

        e9 = data[
            "ema9"
        ][i]

        e20 = data[
            "ema20"
        ][i]

        e50 = data[
            "ema50"
        ][i]

        if (
            e9 is not None
            and e20 is not None
            and e50 is not None
        ):

            if (
                close > e9
                and e9 > e20
                and e20 > e50
            ):

                signals[
                    "EMA_9_20_50"
                ] = "BULLISH"

            elif (
                close < e9
                and e9 < e20
                and e20 < e50
            ):

                signals[
                    "EMA_9_20_50"
                ] = "BEARISH"


    # ========================================================
    # VWAP
    # ========================================================

    if "VWAP" in allowed:

        vwap = data[
            "vwap"
        ][i]

        if vwap is not None:

            if close > vwap:

                signals[
                    "VWAP"
                ] = "BULLISH"

            elif close < vwap:

                signals[
                    "VWAP"
                ] = "BEARISH"


    # ========================================================
    # RSI
    # ========================================================

    if "RSI" in allowed:

        rsi = data[
            "rsi"
        ][i]

        if rsi is not None:

            if rsi >= 55:

                signals[
                    "RSI_55_45"
                ] = "BULLISH"

            elif rsi <= 45:

                signals[
                    "RSI_55_45"
                ] = "BEARISH"


    # ========================================================
    # SUPERTREND
    # ========================================================

    if "SUPERTREND" in allowed:

        st_direction = data[
            "st_direction"
        ][i]

        if st_direction == 1:

            signals[
                "SUPERTREND"
            ] = "BULLISH"

        elif st_direction == -1:

            signals[
                "SUPERTREND"
            ] = "BEARISH"


    # ========================================================
    # STOCHASTIC
    # ========================================================

    if "STOCHASTIC" in allowed:

        stochastic = data[
            "stochastic"
        ][i]

        if stochastic is not None:

            if stochastic >= 60:

                signals[
                    "STOCHASTIC"
                ] = "BULLISH"

            elif stochastic <= 40:

                signals[
                    "STOCHASTIC"
                ] = "BEARISH"


    # ========================================================
    # MOMENTUM
    # ========================================================

    if "MOMENTUM" in allowed:

        momentum = data[
            "momentum"
        ][i]

        if momentum is not None:

            if momentum > 0:

                signals[
                    "MOMENTUM_5"
                ] = "BULLISH"

            elif momentum < 0:

                signals[
                    "MOMENTUM_5"
                ] = "BEARISH"


    # ========================================================
    # VOLUME SPIKE + CANDLE DIRECTION
    # ========================================================

    if "VOLUME_SPIKE" in allowed:

        volume_state = data[
            "volume_spike"
        ][i]

        if volume_state == "SPIKE":

            candle_open = (
                candles[i][
                    "open"
                ]
            )

            if close > candle_open:

                signals[
                    "VOLUME_SPIKE"
                ] = "BULLISH"

            elif close < candle_open:

                signals[
                    "VOLUME_SPIKE"
                ] = "BEARISH"


    # ========================================================
    # ATR EXPANSION + CANDLE DIRECTION
    # ========================================================

    if "ATR" in allowed:

        atr = data[
            "atr"
        ][i]

        if (
            atr is not None
            and i >= 20
        ):

            previous_atr = [
                x
                for x in data[
                    "atr"
                ][
                    i - 20:i
                ]
                if x is not None
            ]

            if previous_atr:

                avg_atr = (
                    sum(
                        previous_atr
                    )
                    / len(
                        previous_atr
                    )
                )

                if (
                    avg_atr > 0
                    and atr
                    >= avg_atr
                    * 1.15
                ):

                    candle_open = (
                        candles[i][
                            "open"
                        ]
                    )

                    if close > candle_open:

                        signals[
                            "ATR_EXPANSION"
                        ] = "BULLISH"

                    elif close < candle_open:

                        signals[
                            "ATR_EXPANSION"
                        ] = "BEARISH"

    return signals


def get_future_result(
    candles,
    i,
    window,
    signal
):

    future_index = (
        i + window
    )

    if future_index >= len(
        candles
    ):

        return None

    entry = candles[i][
        "close"
    ]

    future = candles[
        future_index
    ][
        "close"
    ]

    if entry == 0:

        return None

    move_pct = (
        (
            future
            - entry
        )
        / entry
    ) * 100.0

    if signal == "BULLISH":

        correct = (
            future > entry
        )

    elif signal == "BEARISH":

        correct = (
            future < entry
        )

    else:

        return None

    return {
        "correct": correct,
        "move_pct": move_pct,
    }


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


def record_result(
    stats,
    signal,
    outcome
):

    stats[
        "total"
    ] += 1

    stats[
        "move_sum"
    ] += abs(
        outcome[
            "move_pct"
        ]
    )

    if signal == "BULLISH":

        stats[
            "bullish"
        ] += 1

    elif signal == "BEARISH":

        stats[
            "bearish"
        ] += 1

    if outcome[
        "correct"
    ]:

        stats[
            "correct"
        ] += 1

        if signal == "BULLISH":

            stats[
                "bull_correct"
            ] += 1

        elif signal == "BEARISH":

            stats[
                "bear_correct"
            ] += 1


def research_timeframe(
    candles,
    timeframe
):

    results = defaultdict(
        create_stats
    )

    if len(candles) < 60:

        return results

    data = (
        build_indicator_data(
            candles
        )
    )

    max_window = max(
        FUTURE_WINDOWS
    )

    for i in range(
        50,
        len(candles)
        - max_window
    ):

        signals = (
            get_indicator_signals(
                candles,
                data,
                i,
                timeframe
            )
        )

        for (
            indicator,
            signal
        ) in signals.items():

            for window in (
                FUTURE_WINDOWS
            ):

                outcome = (
                    get_future_result(
                        candles,
                        i,
                        window,
                        signal
                    )
                )

                if outcome is None:
                    continue

                key = (
                    indicator,
                    window
                )

                record_result(
                    results[key],
                    signal,
                    outcome
                )

    return results
def get_indicator_signals(
    candles,
    data,
    i,
    timeframe
):

    signals = {}

    close = candles[i][
        "close"
    ]

    allowed = (
        INDICATOR_TIMEFRAMES[
            timeframe
        ]
    )

    # ========================================================
    # EMA ALIGNMENT
    # ========================================================

    if "EMA" in allowed:

        e9 = data[
            "ema9"
        ][i]

        e20 = data[
            "ema20"
        ][i]

        e50 = data[
            "ema50"
        ][i]

        if (
            e9 is not None
            and e20 is not None
            and e50 is not None
        ):

            if (
                close > e9
                and e9 > e20
                and e20 > e50
            ):

                signals[
                    "EMA_9_20_50"
                ] = "BULLISH"

            elif (
                close < e9
                and e9 < e20
                and e20 < e50
            ):

                signals[
                    "EMA_9_20_50"
                ] = "BEARISH"


    # ========================================================
    # VWAP
    # ========================================================

    if "VWAP" in allowed:

        vwap = data[
            "vwap"
        ][i]

        if vwap is not None:

            if close > vwap:

                signals[
                    "VWAP"
                ] = "BULLISH"

            elif close < vwap:

                signals[
                    "VWAP"
                ] = "BEARISH"


    # ========================================================
    # RSI
    # ========================================================

    if "RSI" in allowed:

        rsi = data[
            "rsi"
        ][i]

        if rsi is not None:

            if rsi >= 55:

                signals[
                    "RSI_55_45"
                ] = "BULLISH"

            elif rsi <= 45:

                signals[
                    "RSI_55_45"
                ] = "BEARISH"


    # ========================================================
    # SUPERTREND
    # ========================================================

    if "SUPERTREND" in allowed:

        st_direction = data[
            "st_direction"
        ][i]

        if st_direction == 1:

            signals[
                "SUPERTREND"
            ] = "BULLISH"

        elif st_direction == -1:

            signals[
                "SUPERTREND"
            ] = "BEARISH"


    # ========================================================
    # STOCHASTIC
    # ========================================================

    if "STOCHASTIC" in allowed:

        stochastic = data[
            "stochastic"
        ][i]

        if stochastic is not None:

            if stochastic >= 60:

                signals[
                    "STOCHASTIC"
                ] = "BULLISH"

            elif stochastic <= 40:

                signals[
                    "STOCHASTIC"
                ] = "BEARISH"


    # ========================================================
    # MOMENTUM
    # ========================================================

    if "MOMENTUM" in allowed:

        momentum = data[
            "momentum"
        ][i]

        if momentum is not None:

            if momentum > 0:

                signals[
                    "MOMENTUM_5"
                ] = "BULLISH"

            elif momentum < 0:

                signals[
                    "MOMENTUM_5"
                ] = "BEARISH"


    # ========================================================
    # VOLUME SPIKE + CANDLE DIRECTION
    # ========================================================

    if "VOLUME_SPIKE" in allowed:

        volume_state = data[
            "volume_spike"
        ][i]

        if volume_state == "SPIKE":

            candle_open = (
                candles[i][
                    "open"
                ]
            )

            if close > candle_open:

                signals[
                    "VOLUME_SPIKE"
                ] = "BULLISH"

            elif close < candle_open:

                signals[
                    "VOLUME_SPIKE"
                ] = "BEARISH"


    # ========================================================
    # ATR EXPANSION + CANDLE DIRECTION
    # ========================================================

    if "ATR" in allowed:

        atr = data[
            "atr"
        ][i]

        if (
            atr is not None
            and i >= 20
        ):

            previous_atr = [
                x
                for x in data[
                    "atr"
                ][
                    i - 20:i
                ]
                if x is not None
            ]

            if previous_atr:

                avg_atr = (
                    sum(
                        previous_atr
                    )
                    / len(
                        previous_atr
                    )
                )

                if (
                    avg_atr > 0
                    and atr
                    >= avg_atr
                    * 1.15
                ):

                    candle_open = (
                        candles[i][
                            "open"
                        ]
                    )

                    if close > candle_open:

                        signals[
                            "ATR_EXPANSION"
                        ] = "BULLISH"

                    elif close < candle_open:

                        signals[
                            "ATR_EXPANSION"
                        ] = "BEARISH"

    return signals


def get_future_result(
    candles,
    i,
    window,
    signal
):

    future_index = (
        i + window
    )

    if future_index >= len(
        candles
    ):

        return None

    entry = candles[i][
        "close"
    ]

    future = candles[
        future_index
    ][
        "close"
    ]

    if entry == 0:

        return None

    move_pct = (
        (
            future
            - entry
        )
        / entry
    ) * 100.0

    if signal == "BULLISH":

        correct = (
            future > entry
        )

    elif signal == "BEARISH":

        correct = (
            future < entry
        )

    else:

        return None

    return {
        "correct": correct,
        "move_pct": move_pct,
    }


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


def record_result(
    stats,
    signal,
    outcome
):

    stats[
        "total"
    ] += 1

    stats[
        "move_sum"
    ] += abs(
        outcome[
            "move_pct"
        ]
    )

    if signal == "BULLISH":

        stats[
            "bullish"
        ] += 1

    elif signal == "BEARISH":

        stats[
            "bearish"
        ] += 1

    if outcome[
        "correct"
    ]:

        stats[
            "correct"
        ] += 1

        if signal == "BULLISH":

            stats[
                "bull_correct"
            ] += 1

        elif signal == "BEARISH":

            stats[
                "bear_correct"
            ] += 1


def research_timeframe(
    candles,
    timeframe
):

    results = defaultdict(
        create_stats
    )

    if len(candles) < 60:

        return results

    data = (
        build_indicator_data(
            candles
        )
    )

    max_window = max(
        FUTURE_WINDOWS
    )

    for i in range(
        50,
        len(candles)
        - max_window
    ):

        signals = (
            get_indicator_signals(
                candles,
                data,
                i,
                timeframe
            )
        )

        for (
            indicator,
            signal
        ) in signals.items():

            for window in (
                FUTURE_WINDOWS
            ):

                outcome = (
                    get_future_result(
                        candles,
                        i,
                        window,
                        signal
                    )
                )

                if outcome is None:
                    continue

                key = (
                    indicator,
                    window
                )

                record_result(
                    results[key],
                    signal,
                    outcome
                )

    return results
def accuracy(
    stats
):

    total = stats[
        "total"
    ]

    if total == 0:
        return 0.0

    return (
        stats[
            "correct"
        ]
        / total
    ) * 100.0


def print_timeframe_results(
    index,
    timeframe,
    results
):

    print(
        "\n"
        + "-" * 100
    )

    print(
        "INDICATOR ACCURACY:",
        index,
        "|",
        timeframe
    )

    ranked = []

    for (
        indicator,
        window
    ), stats in results.items():

        total = stats[
            "total"
        ]

        if total < MIN_SAMPLE_SIZE:
            continue

        acc = accuracy(
            stats
        )

        avg_move = (
            stats[
                "move_sum"
            ]
            / total
        )

        ranked.append(
            (
                acc,
                total,
                indicator,
                window,
                avg_move,
                stats
            )
        )

    ranked.sort(
        key=lambda x: (
            x[0],
            x[1]
        ),
        reverse=True
    )

    if not ranked:

        print(
            "NO RESULT WITH MINIMUM",
            MIN_SAMPLE_SIZE,
            "SAMPLES"
        )

        return

    for (
        acc,
        total,
        indicator,
        window,
        avg_move,
        stats
    ) in ranked:

        bull_acc = 0.0

        if stats[
            "bullish"
        ] > 0:

            bull_acc = (
                stats[
                    "bull_correct"
                ]
                / stats[
                    "bullish"
                ]
            ) * 100.0

        bear_acc = 0.0

        if stats[
            "bearish"
        ] > 0:

            bear_acc = (
                stats[
                    "bear_correct"
                ]
                / stats[
                    "bearish"
                ]
            ) * 100.0

        print(
            f"{indicator:<18} | "
            f"NEXT {window:<2} | "
            f"SAMPLES {total:<4} | "
            f"ACC {acc:>6.2f}% | "
            f"BULL {bull_acc:>6.2f}% | "
            f"BEAR {bear_acc:>6.2f}% | "
            f"AVG MOVE {avg_move:.3f}%"
        )


def merge_results(
    destination,
    source
):

    for key, stats in (
        source.items()
    ):

        target = (
            destination[
                key
            ]
        )

        for field in (
            "total",
            "correct",
            "bullish",
            "bearish",
            "bull_correct",
            "bear_correct",
        ):

            target[
                field
            ] += stats[
                field
            ]

        target[
            "move_sum"
        ] += stats[
            "move_sum"
        ]


def research_index(
    m,
    index
):

    cfg = CONFIG[
        index
    ]

    print(
        "\n"
        + "=" * 100
    )

    print(
        "CONSOLIDATED INDICATOR RESEARCH:",
        index
    )

    print(
        "MAX CANDLES PER TIMEFRAME:",
        MAX_CANDLES
    )

    index_results = {}

    for timeframe, tf_cfg in (
        TIMEFRAMES.items()
    ):

        print(
            "\nFETCHING",
            index,
            timeframe,
            "("
            + tf_cfg[
                "api_interval"
            ]
            + ")"
        )

        rows = fetch_max_950(
            m,
            cfg[
                "segment"
            ],
            cfg[
                "token"
            ],
            tf_cfg[
                "api_interval"
            ],
            tf_cfg[
                "chunk_days"
            ]
        )

        candles = (
            prepare_candles(
                rows
            )
        )

        print(
            "CANDLES:",
            len(
                candles
            )
        )

        if not candles:

            continue

        results = (
            research_timeframe(
                candles,
                timeframe
            )
        )

        index_results[
            timeframe
        ] = results

        print_timeframe_results(
            index,
            timeframe,
            results
        )

    return index_results


def print_combined_results(
    all_results
):

    print(
        "\n"
        + "=" * 100
    )

    print(
        "NIFTY + SENSEX COMBINED "
        "INDICATOR RESEARCH"
    )

    for timeframe in (
        TIMEFRAMES
    ):

        combined = defaultdict(
            create_stats
        )

        for index in (
            "NIFTY",
            "SENSEX"
        ):

            index_data = (
                all_results.get(
                    index,
                    {}
                )
            )

            tf_results = (
                index_data.get(
                    timeframe
                )
            )

            if tf_results:

                merge_results(
                    combined,
                    tf_results
                )

        print_timeframe_results(
            "COMBINED",
            timeframe,
            combined
        )


def print_best_indicators(
    all_results
):

    print(
        "\n"
        + "=" * 100
    )

    print(
        "BEST INDICATOR / TIMEFRAME "
        "SUMMARY"
    )

    for index in (
        "NIFTY",
        "SENSEX"
    ):

        candidates = []

        index_data = (
            all_results.get(
                index,
                {}
            )
        )

        for (
            timeframe,
            results
        ) in index_data.items():

            for (
                indicator,
                window
            ), stats in results.items():

                if stats[
                    "total"
                ] < MIN_SAMPLE_SIZE:

                    continue

                acc = accuracy(
                    stats
                )

                candidates.append(
                    (
                        acc,
                        stats[
                            "total"
                        ],
                        timeframe,
                        indicator,
                        window
                    )
                )

        candidates.sort(
            key=lambda x: (
                x[0],
                x[1]
            ),
            reverse=True
        )

        print(
            "\n",
            index
        )

        if not candidates:

            print(
                "NO QUALIFIED RESULTS"
            )

            continue

        for item in (
            candidates[:10]
        ):

            (
                acc,
                samples,
                timeframe,
                indicator,
                window
            ) = item

            print(
                f"{timeframe:<4} | "
                f"{indicator:<18} | "
                f"NEXT {window:<2} | "
                f"ACC {acc:>6.2f}% | "
                f"SAMPLES {samples}"
            )


def main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token
    )

    all_results = {}

    for index in (
        "NIFTY",
        "SENSEX"
    ):

        try:

            all_results[
                index
            ] = research_index(
                m,
                index
            )

        except Exception as e:

            print(
                "\nERROR",
                index,
                type(e).__name__,
                e
            )

    print_combined_results(
        all_results
    )

    print_best_indicators(
        all_results
    )


if __name__ == "__main__":
    main()
