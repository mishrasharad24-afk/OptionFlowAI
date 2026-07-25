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



def pe_reversal_features(candles, i, ema9, ema20):
    """
    Detect bearish reversal structure before/at current candle.
    Returns a dictionary of PE-specific reversal filters.
    """

    if i < 6:
        return {}

    c0 = candles[i]
    c1 = candles[i - 1]
    c2 = candles[i - 2]
    c3 = candles[i - 3]
    c4 = candles[i - 4]
    c5 = candles[i - 5]

    # Recent bullish/up move before reversal.
    prior_up_3 = (
        c1["c"] > c3["c"]
    )

    prior_up_5 = (
        c1["c"] > c5["c"]
    )

    # Current bearish reversal candle.
    bearish = (
        c0["c"] < c0["o"]
    )

    # Break below previous candle low.
    break_prev_low = (
        c0["c"] < c1["l"]
    )

    # Lower high structure.
    lower_high = (
        c0["h"] < c1["h"]
    )

    # Bearish engulfing body.
    bearish_engulf = (
        bearish
        and c1["c"] > c1["o"]
        and c0["o"] >= c1["c"]
        and c0["c"] <= c1["o"]
    )

    # Close location near candle low.
    candle_range = max(
        c0["h"] - c0["l"],
        1e-9,
    )

    close_near_low = (
        (c0["c"] - c0["l"])
        / candle_range
        <= 0.30
    )

    # EMA rejection / breakdown.
    ema_break = (
        c0["c"] < ema9
    )

    ema_bear = (
        c0["c"] < ema9
        and ema9 < ema20
    )

    # Reversal from above/around EMA9.
    ema_rejection = (
        c0["h"] >= ema9
        and c0["c"] < ema9
    )

    # Downward momentum acceleration.
    momentum_down = (
        c0["c"] < c1["c"]
        and c1["c"] <= c2["c"]
    )

    return {
        "PRIOR_UP_3": prior_up_3,
        "PRIOR_UP_5": prior_up_5,
        "BEARISH": bearish,
        "BREAK_PREV_LOW": break_prev_low,
        "LOWER_HIGH": lower_high,
        "BEARISH_ENGULF": bearish_engulf,
        "CLOSE_NEAR_LOW": close_near_low,
        "EMA_BREAK": ema_break,
        "EMA_BEAR": ema_bear,
        "EMA_REJECTION": ema_rejection,
        "MOMENTUM_DOWN": momentum_down,
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
    print("INDEPENDENT PE REVERSAL RESEARCH")

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

    events = 0

    for i, candle in enumerate(candles):

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

        f = pe_reversal_features(
            candles,
            i,
            ema9,
            ema20,
        )

        if not f:
            continue

        entry = candle["c"]

        favorable = (
            entry
            - min(
                x["l"]
                for x in future
            )
        ) / entry * 100

        adverse = (
            max(
                x["h"]
                for x in future
            )
            - entry
        ) / entry * 100

        bucket = time_bucket(
            candle["dt"]
        )

        tests = {
            "PRIOR_UP3+BEAR":
                f["PRIOR_UP_3"]
                and f["BEARISH"],

            "PRIOR_UP5+BEAR":
                f["PRIOR_UP_5"]
                and f["BEARISH"],

            "UP3+BREAK_LOW":
                f["PRIOR_UP_3"]
                and f["BREAK_PREV_LOW"],

            "UP3+LOWER_HIGH+BEAR":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"],

            "UP3+NEAR_LOW+BEAR":
                f["PRIOR_UP_3"]
                and f["CLOSE_NEAR_LOW"]
                and f["BEARISH"],

            "UP3+EMA_BREAK+BEAR":
                f["PRIOR_UP_3"]
                and f["EMA_BREAK"]
                and f["BEARISH"],

            "UP3+EMA_REJECTION+BEAR":
                f["PRIOR_UP_3"]
                and f["EMA_REJECTION"]
                and f["BEARISH"],

            "UP3+BREAK_LOW+NEAR_LOW":
                f["PRIOR_UP_3"]
                and f["BREAK_PREV_LOW"]
                and f["CLOSE_NEAR_LOW"],

            "UP3+BREAK_LOW+EMA":
                f["PRIOR_UP_3"]
                and f["BREAK_PREV_LOW"]
                and f["EMA_BREAK"],

            "UP5+BREAK_LOW+EMA":
                f["PRIOR_UP_5"]
                and f["BREAK_PREV_LOW"]
                and f["EMA_BREAK"],

            "UP5+BREAK_LOW+EMA+NEAR_LOW":
                f["PRIOR_UP_5"]
                and f["BREAK_PREV_LOW"]
                and f["EMA_BREAK"]
                and f["CLOSE_NEAR_LOW"],

            "BEARISH_ENGULF_AFTER_UP":
                f["PRIOR_UP_3"]
                and f["BEARISH_ENGULF"],
        }

        event_found = False

        for name, ok in tests.items():

            if not ok:
                continue

            event_found = True

            update_stats(
                stats,
                (
                    "PE",
                    name,
                ),
                favorable,
                adverse,
            )

            update_stats(
                stats,
                (
                    "PE",
                    name
                    + "+TIME_"
                    + bucket,
                ),
                favorable,
                adverse,
            )

        if event_found:
            events += 1

    print("CANDLES:", len(candles))
    print("REVERSAL EVENT CANDLES:", events)

    print("\n" + "=" * 100)
    print("FINAL INDEPENDENT PE REVERSAL RESULTS")

    results = []

    for (
        stat_side,
        name
    ), data in stats.items():

        signals = data["signals"]

        if not signals:
            continue

        rate = (
            data["wins"]
            / signals
            * 100
        )

        avg_mfe = (
            data["mfe"]
            / signals
        )

        avg_mae = (
            data["mae"]
            / signals
        )

        results.append(
            (
                rate,
                signals,
                name,
                avg_mfe,
                avg_mae,
            )
        )

    results.sort(
        reverse=True
    )

    for (
        rate,
        signals,
        name,
        avg_mfe,
        avg_mae,
    ) in results:

        print(
            name,
            "| SIGNALS",
            signals,
            "| RATE",
            round(rate, 2),
            "%",
            "| AVG MFE",
            round(avg_mfe, 4),
            "%",
            "| AVG MAE",
            round(avg_mae, 4),
            "%",
        )


if __name__ == "__main__":
    main()
