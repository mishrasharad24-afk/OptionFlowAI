import sys
import os
from datetime import datetime, timedelta

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY


TOKEN_FILE = (
    "/home/ec2-user/OptionFlowAI/"
    "access_token.txt"
)

MAX_CANDLES = 950

CONFIG = {
    "NIFTY": {
        "segment": "NSE",
        "token": "26000",
    },
    "SENSEX": {
        "segment": "BSE",
        "token": "51",
    },
}

TIMEFRAMES = {
    "1M": {
        "api_interval": "minute",
        "chunk_days": 2,
    },
    "5M": {
        "api_interval": "5minute",
        "chunk_days": 7,
    },
    "15M": {
        "api_interval": "15minute",
        "chunk_days": 20,
    },
    "60M": {
        "api_interval": "60minute",
        "chunk_days": 80,
    },
    "DAY": {
        "api_interval": "day",
        "chunk_days": 1000,
    },
}


def get_candles(response):

    if response is None:
        return []

    try:
        data = response.json()
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    return (
        data.get(
            "data",
            {}
        ).get(
            "candles",
            []
        )
        or []
    )


def fetch_chunk(
    m,
    segment,
    token,
    interval,
    from_date,
    to_date
):

    response = m.get_historical_chart(
        segment,
        str(token),
        interval,
        from_date,
        to_date
    )

    return get_candles(
        response
    )


def fetch_max_950(
    m,
    segment,
    token,
    interval,
    chunk_days
):

    all_rows = []

    end = datetime.now()

    cursor_end = end

    max_loops = 100

    loops = 0

    while (
        len(all_rows) < MAX_CANDLES
        and loops < max_loops
    ):

        loops += 1

        cursor_start = (
            cursor_end
            - timedelta(
                days=chunk_days
            )
        )

        try:

            rows = fetch_chunk(
                m,
                segment,
                token,
                interval,
                cursor_start.strftime(
                    "%Y-%m-%d"
                ),
                cursor_end.strftime(
                    "%Y-%m-%d"
                )
            )

        except Exception as e:

            print(
                "FETCH ERROR",
                interval,
                cursor_start.strftime(
                    "%Y-%m-%d"
                ),
                cursor_end.strftime(
                    "%Y-%m-%d"
                ),
                type(e).__name__,
                e
            )

            cursor_end = (
                cursor_start
                - timedelta(days=1)
            )

            continue

        if rows:

            all_rows.extend(
                rows
            )

        cursor_end = (
            cursor_start
            - timedelta(days=1)
        )

    unique = {
        row[0]: row
        for row in all_rows
        if row
    }

    rows = sorted(
        unique.values(),
        key=lambda x: x[0]
    )

    if len(rows) > MAX_CANDLES:

        rows = rows[
            -MAX_CANDLES:
        ]

    return rows


def candle_direction(
    candle
):

    open_price = float(
        candle[1]
    )

    close_price = float(
        candle[4]
    )

    if close_price > open_price:
        return "BULL"

    if close_price < open_price:
        return "BEAR"

    return "FLAT"


def calculate_context(
    rows
):

    if not rows:

        return {
            "count": 0,
            "trend": "NO_DATA",
            "momentum": "NO_DATA",
            "range": 0,
            "change_pct": 0,
        }

    first_close = float(
        rows[0][4]
    )

    last_close = float(
        rows[-1][4]
    )

    highest = max(
        float(x[2])
        for x in rows
    )

    lowest = min(
        float(x[3])
        for x in rows
    )

    total_range = (
        highest - lowest
    )

    if first_close:

        change_pct = (
            (
                last_close
                - first_close
            )
            / first_close
        ) * 100

    else:

        change_pct = 0

    recent = rows[
        -min(
            20,
            len(rows)
        ):
    ]

    bull = 0
    bear = 0

    for candle in recent:

        direction = (
            candle_direction(
                candle
            )
        )

        if direction == "BULL":
            bull += 1

        elif direction == "BEAR":
            bear += 1

    if change_pct >= 0.50:

        trend = "BULLISH"

    elif change_pct <= -0.50:

        trend = "BEARISH"

    else:

        trend = "RANGE"

    if bull >= bear + 4:

        momentum = "BULLISH"

    elif bear >= bull + 4:

        momentum = "BEARISH"

    else:

        momentum = "MIXED"

    return {
        "count": len(rows),
        "trend": trend,
        "momentum": momentum,
        "range": total_range,
        "change_pct": change_pct,
        "first": rows[0][0],
        "last": rows[-1][0],
        "last_close": last_close,
    }


def determine_mtf_bias(
    contexts
):

    score = 0

    weights = {
        "1M": 1,
        "5M": 2,
        "15M": 3,
        "60M": 4,
        "DAY": 5,
    }

    for timeframe, weight in (
        weights.items()
    ):

        context = contexts.get(
            timeframe,
            {}
        )

        trend = context.get(
            "trend"
        )

        momentum = context.get(
            "momentum"
        )

        if trend == "BULLISH":
            score += weight

        elif trend == "BEARISH":
            score -= weight

        if momentum == "BULLISH":
            score += 1

        elif momentum == "BEARISH":
            score -= 1

    if score >= 9:

        bias = "STRONG_BULLISH"

    elif score >= 4:

        bias = "BULLISH"

    elif score <= -9:

        bias = "STRONG_BEARISH"

    elif score <= -4:

        bias = "BEARISH"

    else:

        bias = "MIXED"

    return bias, score


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
        "MULTI TIMEFRAME RESEARCH:",
        index
    )

    print(
        "MAX CANDLES PER TIMEFRAME:",
        MAX_CANDLES
    )

    contexts = {}

    for timeframe, tf_cfg in (
        TIMEFRAMES.items()
    ):

        print(
            "\nFETCHING",
            timeframe,
            "(",
            tf_cfg[
                "api_interval"
            ],
            ")"
        )

        rows = fetch_max_950(
            m,
            cfg["segment"],
            cfg["token"],
            tf_cfg[
                "api_interval"
            ],
            tf_cfg[
                "chunk_days"
            ]
        )

        context = (
            calculate_context(
                rows
            )
        )

        contexts[
            timeframe
        ] = context

        print(
            "CANDLES :",
            context[
                "count"
            ]
        )

        if not rows:

            print(
                "STATUS  : NO DATA"
            )

            continue

        print(
            "FIRST   :",
            context[
                "first"
            ]
        )

        print(
            "LAST    :",
            context[
                "last"
            ]
        )

        print(
            "CHANGE  :",
            f"{context['change_pct']:+.2f}%"
        )

        print(
            "TREND   :",
            context[
                "trend"
            ]
        )

        print(
            "MOMENTUM:",
            context[
                "momentum"
            ]
        )

    bias, score = (
        determine_mtf_bias(
            contexts
        )
    )

    print(
        "\n"
        + "-" * 100
    )

    print(
        "MTF RESEARCH SUMMARY:",
        index
    )

    for timeframe in (
        "1M",
        "5M",
        "15M",
        "60M",
        "DAY"
    ):

        context = contexts.get(
            timeframe,
            {}
        )

        print(
            f"{timeframe:>3} | "
            f"CANDLES "
            f"{context.get('count', 0):>3} | "
            f"TREND "
            f"{context.get('trend', 'NO_DATA'):<8} | "
            f"MOMENTUM "
            f"{context.get('momentum', 'NO_DATA'):<8} | "
            f"CHANGE "
            f"{context.get('change_pct', 0):+.2f}%"
        )

    print(
        "\nMTF SCORE :",
        score
    )

    print(
        "MTF BIAS  :",
        bias
    )

    return {
        "index": index,
        "contexts": contexts,
        "score": score,
        "bias": bias,
    }


def main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token
    )

    final_results = {}

    for index in (
        "NIFTY",
        "SENSEX"
    ):

        try:

            result = (
                research_index(
                    m,
                    index
                )
            )

            final_results[
                index
            ] = result

        except Exception as e:

            print(
                "\nERROR",
                index,
                type(e).__name__,
                e
            )

    print(
        "\n"
        + "=" * 100
    )

    print(
        "FINAL MULTI TIMEFRAME RESEARCH"
    )

    for index, result in (
        final_results.items()
    ):

        print(
            index,
            "| SCORE:",
            result["score"],
            "| BIAS:",
            result["bias"]
        )


if __name__ == "__main__":
    main()
