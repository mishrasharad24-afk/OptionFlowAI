from collections import defaultdict

from historical.curve_option_backtest import (
    MConnect,
    API_KEY,
    TOKEN_FILE,
    fetch_spot_history,
    find_curve_signals,
    parse,
)

FORWARD = 5

STRENGTH_LEVELS = (
    0.50,
    0.60,
    0.70,
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


def candle_strength(candle):
    rng = (
        candle["h"]
        - candle["l"]
    )

    if rng <= 0:
        return 0

    body = abs(
        candle["c"]
        - candle["o"]
    )

    return body / rng


def time_bucket(dt):
    t = dt.time()

    if t.hour < 11:
        return "OPEN_0915_1100"

    if t.hour < 13:
        return "MID_1100_1300"

    if (
        t.hour < 14
        or (
            t.hour == 14
            and t.minute < 30
        )
    ):
        return "AFTERNOON_1300_1430"

    return "LATE_1430_CLOSE"


def new_stats():
    return {
        "signals": 0,
        "wins": 0,
        "mfe": 0.0,
        "mae": 0.0,
    }


def update_stats(
    stats,
    key,
    favorable,
    adverse,
):
    s = stats[key]

    s["signals"] += 1
    s["mfe"] += favorable
    s["mae"] += adverse

    if favorable > adverse:
        s["wins"] += 1


def main():
    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("=" * 100)
    print("ADVANCED CURVE FILTER RESEARCH")

    rows = fetch_spot_history(m)

    candles = [
        parse(row)
        for row in rows
    ]

    candles = [
        x for x in candles
        if x
    ]

    signals = find_curve_signals(rows)

    signal_map = {
        x["dt"]: x
        for x in signals
    }

    stats = defaultdict(
        new_stats
    )

    matched = 0

    for i, candle in enumerate(candles):

        signal = signal_map.get(
            candle["dt"]
        )

        if not signal:
            continue

        if i < 20:
            continue

        future = candles[
            i + 1:
            i + 1 + FORWARD
        ]

        future = [
            x for x in future
            if x["dt"].date()
            == candle["dt"].date()
        ]

        if not future:
            continue

        matched += 1

        side = signal["side"]
        entry = candle["c"]

        closes = [
            x["c"]
            for x in candles[
                i - 20:
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

        strength = candle_strength(
            candle
        )

        bucket = time_bucket(
            candle["dt"]
        )

        if side == "CE":
            favorable = (
                max(x["h"] for x in future)
                - entry
            ) / entry * 100

            adverse = (
                entry
                - min(x["l"] for x in future)
            ) / entry * 100

            directional = (
                candle["c"]
                > candle["o"]
            )

            ema_ok = (
                candle["c"] > ema9
                and ema9 > ema20
            )

        else:
            favorable = (
                entry
                - min(x["l"] for x in future)
            ) / entry * 100

            adverse = (
                max(x["h"] for x in future)
                - entry
            ) / entry * 100

            directional = (
                candle["c"]
                < candle["o"]
            )

            ema_ok = (
                candle["c"] < ema9
                and ema9 < ema20
            )

        update_stats(
            stats,
            (
                side,
                "CURVE_ONLY",
            ),
            favorable,
            adverse,
        )

        update_stats(
            stats,
            (
                side,
                "TIME_" + bucket,
            ),
            favorable,
            adverse,
        )

        for level in STRENGTH_LEVELS:

            label = int(
                level * 100
            )

            if (
                directional
                and strength >= level
            ):
                update_stats(
                    stats,
                    (
                        side,
                        f"STRONG_{label}",
                    ),
                    favorable,
                    adverse,
                )

                update_stats(
                    stats,
                    (
                        side,
                        f"STRONG_{label}+TIME_{bucket}",
                    ),
                    favorable,
                    adverse,
                )

                if ema_ok:
                    update_stats(
                        stats,
                        (
                            side,
                            f"EMA+STRONG_{label}",
                        ),
                        favorable,
                        adverse,
                    )

                    update_stats(
                        stats,
                        (
                            side,
                            f"EMA+STRONG_{label}+TIME_{bucket}",
                        ),
                        favorable,
                        adverse,
                    )

    print("CANDLES:", len(candles))
    print("CURVE SIGNALS:", len(signals))
    print("MATCHED:", matched)

    print("\n" + "=" * 100)
    print("FINAL ADVANCED RESULTS")

    for side in ("CE", "PE"):

        print("\nSIDE:", side)

        results = []

        for (
            stat_side,
            name
        ), s in stats.items():

            if stat_side != side:
                continue

            total = s["signals"]

            if total == 0:
                continue

            results.append((
                s["wins"] / total * 100,
                total,
                name,
                s["mfe"] / total,
                s["mae"] / total,
            ))

        results.sort(
            reverse=True
        )

        for (
            rate,
            total,
            name,
            mfe,
            mae,
        ) in results:

            print(
                name,
                "| SIGNALS",
                total,
                "| RATE",
                round(rate, 2),
                "%",
                "| AVG MFE",
                round(mfe, 4),
                "%",
                "| AVG MAE",
                round(mae, 4),
                "%",
            )


if __name__ == "__main__":
    main()
