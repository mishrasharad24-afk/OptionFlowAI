from collections import defaultdict

from historical.curve_option_backtest import (
    MConnect,
    API_KEY,
    TOKEN_FILE,
    fetch_spot_history,
    find_curve_signals,
    parse,
)


FORWARD_WINDOWS = (1, 3, 5)

# Basic trend/momentum periods
EMA_FAST = 9
EMA_SLOW = 20


def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    value = sum(
        values[:period]
    ) / period

    for price in values[period:]:
        value = (
            price * multiplier
            + value * (1 - multiplier)
        )

    return value


def candle_strength(candle):
    total_range = (
        candle["h"]
        - candle["l"]
    )

    if total_range <= 0:
        return 0

    body = abs(
        candle["c"]
        - candle["o"]
    )

    return (
        body / total_range
    )


def prepare_candles(rows):
    candles = [
        parse(row)
        for row in rows
    ]

    return [
        x for x in candles
        if x
    ]


def build_signal_map(signals):
    return {
        signal["dt"]: signal
        for signal in signals
    }


def create_stats():
    return {
        "signals": 0,
        "wins": 0,
        "move": 0.0,
        "adverse": 0.0,
    }

def classify_signal(
    candles,
    index,
    signal,
):
    current = candles[index]

    closes = [
        x["c"]
        for x in candles[
            max(0, index - 60):
            index + 1
        ]
    ]

    ema9 = ema(
        closes,
        EMA_FAST,
    )

    ema20 = ema(
        closes,
        EMA_SLOW,
    )

    if (
        ema9 is None
        or ema20 is None
    ):
        return None

    side = signal["side"]

    # ===== EMA ALIGNMENT =====
    if side == "CE":
        ema_aligned = (
            current["c"] > ema9
            and ema9 > ema20
        )

    else:
        ema_aligned = (
            current["c"] < ema9
            and ema9 < ema20
        )

    # ===== STRONG CANDLE =====
    strength = candle_strength(
        current
    )

    strong_candle = (
        strength >= 0.60
    )

    # Candle direction must also
    # agree with curve direction
    if side == "CE":
        direction_candle = (
            current["c"]
            > current["o"]
        )
    else:
        direction_candle = (
            current["c"]
            < current["o"]
        )

    strong_directional = (
        strong_candle
        and direction_candle
    )

    # ===== 3-CANDLE MOMENTUM =====
    momentum_ok = False

    if index >= 2:

        c0 = candles[index - 2]["c"]
        c1 = candles[index - 1]["c"]
        c2 = candles[index]["c"]

        if side == "CE":
            momentum_ok = (
                c2 > c1 > c0
            )

        else:
            momentum_ok = (
                c2 < c1 < c0
            )

    filters = []

    # Base curve signal
    filters.append(
        "CURVE_ONLY"
    )

    if ema_aligned:
        filters.append(
            "CURVE+EMA"
        )

    if strong_directional:
        filters.append(
            "CURVE+STRONG"
        )

    if momentum_ok:
        filters.append(
            "CURVE+MOMENTUM"
        )

    if (
        ema_aligned
        and strong_directional
    ):
        filters.append(
            "CURVE+EMA+STRONG"
        )

    if (
        ema_aligned
        and momentum_ok
    ):
        filters.append(
            "CURVE+EMA+MOMENTUM"
        )

    if (
        strong_directional
        and momentum_ok
    ):
        filters.append(
            "CURVE+STRONG+MOMENTUM"
        )

    if (
        ema_aligned
        and strong_directional
        and momentum_ok
    ):
        filters.append(
            "CURVE+EMA+STRONG+MOMENTUM"
        )

    return {
        "side": side,
        "filters": filters,
        "ema_aligned": ema_aligned,
        "strong": strong_directional,
        "momentum": momentum_ok,
        "strength": strength,
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
    print("NIFTY CURVE FILTER RESEARCH")

    rows = fetch_spot_history(m)
    candles = prepare_candles(rows)

    signals = find_curve_signals(rows)
    signal_map = build_signal_map(signals)

    print(
        "SPOT CANDLES:",
        len(candles)
    )

    print(
        "CURVE SIGNALS:",
        len(signals)
    )

    stats = {
        "CE": defaultdict(
            create_stats
        ),
        "PE": defaultdict(
            create_stats
        ),
    }

    matched = 0

    for i, candle in enumerate(candles):

        signal = signal_map.get(
            candle["dt"]
        )

        if not signal:
            continue

        classification = classify_signal(
            candles,
            i,
            signal,
        )

        if not classification:
            continue

        matched += 1

        side = classification["side"]

        entry = candle["c"]

        if entry <= 0:
            continue

        for forward in FORWARD_WINDOWS:

            future = candles[
                i + 1:
                i + 1 + forward
            ]

            # Do not cross into next trading day
            future = [
                x for x in future
                if x["dt"].date()
                == candle["dt"].date()
            ]

            if not future:
                continue

            high = max(
                x["h"]
                for x in future
            )

            low = min(
                x["l"]
                for x in future
            )

            if side == "CE":

                favorable = (
                    (high - entry)
                    / entry
                ) * 100

                adverse = (
                    (entry - low)
                    / entry
                ) * 100

            else:

                favorable = (
                    (entry - low)
                    / entry
                ) * 100

                adverse = (
                    (high - entry)
                    / entry
                ) * 100

            for filter_name in classification[
                "filters"
            ]:

                key = (
                    filter_name,
                    forward,
                )

                s = stats[
                    side
                ][key]

                s["signals"] += 1
                s["move"] += favorable
                s["adverse"] += adverse

                if favorable > adverse:
                    s["wins"] += 1

    print(
        "MATCHED SIGNALS:",
        matched
    )

    print(
        "\n" + "=" * 100
    )

    print(
        "FINAL CURVE FILTER RESULTS"
    )

    for side in (
        "CE",
        "PE",
    ):

        print(
            "\nSIDE:",
            side
        )

        results = []

        for key, s in stats[
            side
        ].items():

            filter_name, forward = key

            total = s["signals"]

            if total == 0:
                continue

            rate = (
                s["wins"]
                / total
            ) * 100

            avg_move = (
                s["move"]
                / total
            )

            avg_adverse = (
                s["adverse"]
                / total
            )

            results.append({
                "filter": filter_name,
                "forward": forward,
                "signals": total,
                "wins": s["wins"],
                "rate": rate,
                "move": avg_move,
                "adverse": avg_adverse,
            })

        # Highest win rate first.
        # For equal rate, prefer larger sample.
        results.sort(
            key=lambda x: (
                x["rate"],
                x["signals"],
            ),
            reverse=True,
        )

        for r in results:

            print(
                r["filter"],
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
                    r["move"],
                    4
                ),
                "%",
                "| AVG MAE",
                round(
                    r["adverse"],
                    4
                ),
                "%",
            )


if __name__ == "__main__":
    main()
