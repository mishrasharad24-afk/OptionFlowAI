from collections import defaultdict

from historical.curve_option_backtest import (
    MConnect,
    API_KEY,
    TOKEN_FILE,
    fetch_spot_history,
    parse,
)

FORWARD_WINDOWS = (1, 3, 5)

CURVE_LENGTHS = (
    3,
    4,
    5,
)


def ema(values, period):
    if len(values) < period:
        return None

    k = 2 / (period + 1)

    value = sum(
        values[:period]
    ) / period

    for price in values[period:]:
        value = (
            price * k
            + value * (1 - k)
        )

    return value


def body_strength(candle):
    rng = candle["h"] - candle["l"]

    if rng <= 0:
        return 0.0

    return abs(
        candle["c"] - candle["o"]
    ) / rng


def close_near_low(candle):
    rng = candle["h"] - candle["l"]

    if rng <= 0:
        return False

    position = (
        candle["c"] - candle["l"]
    ) / rng

    # Close in bottom 30% of candle
    return position <= 0.30


def strictly_falling(values):
    return all(
        values[i] < values[i - 1]
        for i in range(1, len(values))
    )


def bearish_acceleration(candles):
    if len(candles) < 3:
        return False

    closes = [
        x["c"]
        for x in candles
    ]

    drops = [
        closes[i - 1] - closes[i]
        for i in range(1, len(closes))
    ]

    # Latest downward move must be
    # stronger than previous downward move
    return (
        drops[-1] > 0
        and drops[-2] > 0
        and drops[-1] > drops[-2]
    )


def detect_pe_patterns(
    candles,
    index,
):
    patterns = []

    for length in CURVE_LENGTHS:

        if index < length - 1:
            continue

        group = candles[
            index - length + 1:
            index + 1
        ]

        # Never build a curve across
        # two different trading days
        if len({
            x["dt"].date()
            for x in group
        }) != 1:
            continue

        closes = [
            x["c"]
            for x in group
        ]

        highs = [
            x["h"]
            for x in group
        ]

        lows = [
            x["l"]
            for x in group
        ]

        lower_close = strictly_falling(
            closes
        )

        lower_high = strictly_falling(
            highs
        )

        lower_low = strictly_falling(
            lows
        )

        current = group[-1]

        bearish_candle = (
            current["c"]
            < current["o"]
        )

        strong_50 = (
            bearish_candle
            and body_strength(current)
            >= 0.50
        )

        near_low = close_near_low(
            current
        )

        acceleration = bearish_acceleration(
            group
        )

        if lower_close:
            patterns.append(
                f"PE{length}_LOWER_CLOSE"
            )

        if (
            lower_close
            and lower_high
            and lower_low
        ):
            patterns.append(
                f"PE{length}_FULL_STAIR"
            )

        if (
            lower_close
            and lower_high
            and lower_low
            and near_low
        ):
            patterns.append(
                f"PE{length}_FULL_STAIR+NEAR_LOW"
            )

        if (
            lower_close
            and lower_high
            and lower_low
            and strong_50
        ):
            patterns.append(
                f"PE{length}_FULL_STAIR+STRONG"
            )

        if (
            lower_close
            and lower_high
            and lower_low
            and acceleration
        ):
            patterns.append(
                f"PE{length}_FULL_STAIR+ACCEL"
            )

        if (
            lower_close
            and lower_high
            and lower_low
            and near_low
            and strong_50
            and acceleration
        ):
            patterns.append(
                f"PE{length}_STRICT_ALL"
            )

    return patterns


def new_stats():
    return {
        "signals": 0,
        "wins": 0,
        "mfe": 0.0,
        "mae": 0.0,
    }

def main():
    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("=" * 100)
    print("PE STRICT CURVE RESEARCH")

    rows = fetch_spot_history(m)

    candles = [
        parse(row)
        for row in rows
    ]

    candles = [
        x for x in candles
        if x
    ]

    stats = defaultdict(
        new_stats
    )

    total_pattern_events = 0

    for i, candle in enumerate(candles):

        patterns = detect_pe_patterns(
            candles,
            i,
        )

        if not patterns:
            continue

        total_pattern_events += 1

        entry = candle["c"]

        if entry <= 0:
            continue

        # EMA alignment
        closes = [
            x["c"]
            for x in candles[
                max(0, i - 30):
                i + 1
            ]
        ]

        ema9 = ema(
            closes,
            9,
        )

        ema20 = ema(
            closes,
            20,
        )

        ema_bearish = (
            ema9 is not None
            and ema20 is not None
            and entry < ema9
            and ema9 < ema20
        )

        for forward in FORWARD_WINDOWS:

            future = candles[
                i + 1:
                i + 1 + forward
            ]

            # Do not cross trading day
            future = [
                x for x in future
                if x["dt"].date()
                == candle["dt"].date()
            ]

            if not future:
                continue

            future_low = min(
                x["l"]
                for x in future
            )

            future_high = max(
                x["h"]
                for x in future
            )

            # PE / bearish direction:
            # downside = favorable
            favorable = (
                entry - future_low
            ) / entry * 100

            adverse = (
                future_high - entry
            ) / entry * 100

            for pattern in patterns:

                keys = [
                    (
                        pattern,
                        forward,
                    )
                ]

                if ema_bearish:
                    keys.append(
                        (
                            pattern + "+EMA",
                            forward,
                        )
                    )

                for key in keys:

                    s = stats[key]

                    s["signals"] += 1
                    s["mfe"] += favorable
                    s["mae"] += adverse

                    if favorable > adverse:
                        s["wins"] += 1

    print(
        "CANDLES:",
        len(candles)
    )

    print(
        "PATTERN EVENTS:",
        total_pattern_events
    )

    print(
        "\n" + "=" * 100
    )

    print(
        "FINAL PE STRICT CURVE RESULTS"
    )

    results = []

    for (
        pattern,
        forward
    ), s in stats.items():

        total = s["signals"]

        if total == 0:
            continue

        rate = (
            s["wins"]
            / total
            * 100
        )

        avg_mfe = (
            s["mfe"]
            / total
        )

        avg_mae = (
            s["mae"]
            / total
        )

        results.append({
            "pattern": pattern,
            "forward": forward,
            "signals": total,
            "wins": s["wins"],
            "rate": rate,
            "mfe": avg_mfe,
            "mae": avg_mae,
        })

    # Prefer high win rate,
    # then larger sample size
    results.sort(
        key=lambda x: (
            x["rate"],
            x["signals"],
        ),
        reverse=True,
    )

    for r in results:

        print(
            r["pattern"],
            "| NEXT",
            r["forward"],
            "| SIGNALS",
            r["signals"],
            "| WINS",
            r["wins"],
            "| RATE",
            round(
                r["rate"],
                2
            ),
            "%",
            "| AVG MFE",
            round(
                r["mfe"],
                4
            ),
            "%",
            "| AVG MAE",
            round(
                r["mae"],
                4
            ),
            "%",
        )


if __name__ == "__main__":
    main()
