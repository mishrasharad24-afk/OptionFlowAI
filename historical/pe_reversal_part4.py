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

            # PART 3:
            # Refine the strongest independent PE base:
            # UP3 + LOWER_HIGH + BEAR.
            "P3_BASE":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"],

            "P3_BASE+EMA_BEAR":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["EMA_BEAR"],

            "P3_BASE+EMA_REJECTION":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["EMA_REJECTION"],

            "P3_BASE+BREAK_LOW":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["BREAK_PREV_LOW"],

            "P3_BASE+NEAR_LOW":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["CLOSE_NEAR_LOW"],

            "P3_BASE+MOMENTUM":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["MOMENTUM_DOWN"],

            "P3_BASE+BREAK_LOW+EMA_BEAR":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["BREAK_PREV_LOW"]
                and f["EMA_BEAR"],

            "P3_BASE+NEAR_LOW+EMA_BEAR":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["CLOSE_NEAR_LOW"]
                and f["EMA_BEAR"],

            "P3_BASE+BREAK_LOW+NEAR_LOW":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["BREAK_PREV_LOW"]
                and f["CLOSE_NEAR_LOW"],

            "P3_BASE+BREAK_LOW+MOMENTUM":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["BREAK_PREV_LOW"]
                and f["MOMENTUM_DOWN"],

            "P3_BASE+STRONG50":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and candle_strength(candle) >= 0.50,

            "P3_BASE+STRONG60":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and candle_strength(candle) >= 0.60,

            "P3_BASE+STRONG70":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and candle_strength(candle) >= 0.70,

            "P3_BASE+STRONG60+EMA_BEAR":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and candle_strength(candle) >= 0.60
                and f["EMA_BEAR"],

            "P3_BASE+STRONG60+BREAK_LOW":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and candle_strength(candle) >= 0.60
                and f["BREAK_PREV_LOW"],

            "P3_BASE+STRONG60+MOMENTUM":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and candle_strength(candle) >= 0.60
                and f["MOMENTUM_DOWN"],
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



# =============================================================================
# PART 4 - REALISTIC PE REVERSAL TRADE SIMULATOR
# Historical research only. Does not touch the live bot.
# =============================================================================

P4_FORWARD = 5

P4_TARGETS = (
    0.10,
    0.15,
    0.20,
)

P4_STOPS = (
    0.10,
    0.15,
)


def p4_new_stats():
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "unresolved": 0,
    }


def p4_bucket_allowed(bucket, mode):
    if mode == "MID":
        return bucket == "MID_1100_1300"

    if mode == "AFTERNOON":
        return bucket == "AFTERNOON_1300_1430"

    if mode == "LATE":
        return bucket == "LATE_1430_CLOSE"

    if mode == "MID_LATE":
        return bucket in (
            "MID_1100_1300",
            "LATE_1430_CLOSE",
        )

    return False


def p4_simulate_short(entry, future, target_pct, stop_pct):
    """
    Simulates bearish SPOT move corresponding to PE reversal thesis.

    TARGET:
        Spot falls target_pct below entry.

    STOP:
        Spot rises stop_pct above entry.

    Conservative rule:
        If both target and stop are touched in the same candle,
        count STOP first because intrabar sequence is unknown.
    """

    target_price = entry * (
        1.0 - target_pct / 100.0
    )

    stop_price = entry * (
        1.0 + stop_pct / 100.0
    )

    for candle in future:

        stop_hit = (
            candle["h"] >= stop_price
        )

        target_hit = (
            candle["l"] <= target_price
        )

        # Conservative assumption when both occur
        # inside the same OHLC candle.
        if stop_hit and target_hit:
            return "LOSS"

        if stop_hit:
            return "LOSS"

        if target_hit:
            return "WIN"

    return "UNRESOLVED"


def part4_main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("\n" + "=" * 100)
    print("PART 4 - REALISTIC PE REVERSAL TRADE SIMULATOR")
    print("ENTRY: NEXT-CANDLE BEARISH CONFIRMATION")
    print("HOLDING HORIZON:", P4_FORWARD, "CANDLES")
    print("SAME-CANDLE TARGET+SL: CONSERVATIVE SL-FIRST")
    print("=" * 100)

    rows = fetch_spot_history(m)

    candles = [
        parse(row)
        for row in rows
    ]

    candles = [
        x for x in candles
        if x
    ]

    trade_stats = defaultdict(
        p4_new_stats
    )

    raw_signals = 0
    confirmed_entries = 0

    for i, signal_candle in enumerate(candles):

        if i < 20:
            continue

        # Need one confirmation candle plus
        # P4_FORWARD execution candles.
        if i + 1 >= len(candles):
            continue

        confirm = candles[i + 1]

        # Never cross trading days.
        if (
            confirm["dt"].date()
            != signal_candle["dt"].date()
        ):
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

        if (
            ema9 is None
            or ema20 is None
        ):
            continue

        f = pe_reversal_features(
            candles,
            i,
            ema9,
            ema20,
        )

        if not f:
            continue

        # -------------------------------------------------------------
        # Selected Part-3 candidates.
        # We intentionally test multiple candidates independently.
        # -------------------------------------------------------------

        setups = {

            "P4_BASE":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"],

            "P4_BREAK_LOW_EMA_BEAR":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["BREAK_PREV_LOW"]
                and f["EMA_BEAR"],

            "P4_MOMENTUM":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["MOMENTUM_DOWN"],

            "P4_BREAK_LOW_MOMENTUM":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["BREAK_PREV_LOW"]
                and f["MOMENTUM_DOWN"],

            "P4_STRONG60_MOMENTUM":
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and candle_strength(
                    signal_candle
                ) >= 0.60
                and f["MOMENTUM_DOWN"],
        }

        active_setups = [
            name
            for name, ok in setups.items()
            if ok
        ]

        if not active_setups:
            continue

        raw_signals += 1

        # -------------------------------------------------------------
        # NEXT-CANDLE CONFIRMATION
        #
        # Confirmation requires:
        # 1. bearish confirmation candle
        # 2. confirmation close below signal close
        #
        # Entry is confirmation candle CLOSE.
        # This avoids look-ahead entry on the original signal candle.
        # -------------------------------------------------------------

        confirmed = (
            confirm["c"] < confirm["o"]
            and confirm["c"] < signal_candle["c"]
        )

        if not confirmed:
            continue

        entry = confirm["c"]

        confirmed_entries += 1

        # Execution starts AFTER confirmation candle.
        future = candles[
            i + 2:
            i + 2 + P4_FORWARD
        ]

        future = [
            x for x in future
            if (
                x["dt"].date()
                == signal_candle["dt"].date()
            )
        ]

        if not future:
            continue

        bucket = time_bucket(
            signal_candle["dt"]
        )

        modes = (
            "MID",
            "AFTERNOON",
            "LATE",
            "MID_LATE",
        )

        for setup_name in active_setups:

            for mode in modes:

                if not p4_bucket_allowed(
                    bucket,
                    mode,
                ):
                    continue

                for target_pct in P4_TARGETS:

                    for stop_pct in P4_STOPS:

                        result = p4_simulate_short(
                            entry,
                            future,
                            target_pct,
                            stop_pct,
                        )

                        key = (
                            setup_name,
                            mode,
                            target_pct,
                            stop_pct,
                        )

                        st = trade_stats[key]

                        st["trades"] += 1

                        if result == "WIN":
                            st["wins"] += 1

                        elif result == "LOSS":
                            st["losses"] += 1

                        else:
                            st["unresolved"] += 1

    print(
        "CANDLES:",
        len(candles),
    )

    print(
        "RAW P4 SIGNAL EVENTS:",
        raw_signals,
    )

    print(
        "NEXT-CANDLE CONFIRMED EVENTS:",
        confirmed_entries,
    )

    print("\n" + "=" * 100)
    print("PART 4 FINAL REALISTIC RESULTS")
    print("=" * 100)

    results = []

    for (
        setup_name,
        mode,
        target_pct,
        stop_pct,
    ), st in trade_stats.items():

        trades = st["trades"]

        if not trades:
            continue

        resolved = (
            st["wins"]
            + st["losses"]
        )

        win_rate_resolved = (
            st["wins"]
            / resolved
            * 100
            if resolved
            else 0.0
        )

        win_rate_all = (
            st["wins"]
            / trades
            * 100
        )

        results.append(
            (
                win_rate_all,
                win_rate_resolved,
                trades,
                setup_name,
                mode,
                target_pct,
                stop_pct,
                st["wins"],
                st["losses"],
                st["unresolved"],
            )
        )

    results.sort(
        reverse=True
    )

    for (
        win_rate_all,
        win_rate_resolved,
        trades,
        setup_name,
        mode,
        target_pct,
        stop_pct,
        wins,
        losses,
        unresolved,
    ) in results:

        print(
            setup_name,
            "|",
            mode,
            "| TARGET",
            target_pct,
            "%",
            "| SL",
            stop_pct,
            "%",
            "| TRADES",
            trades,
            "| WINS",
            wins,
            "| LOSSES",
            losses,
            "| UNRESOLVED",
            unresolved,
            "| WIN_ALL",
            round(
                win_rate_all,
                2,
            ),
            "%",
            "| WIN_RESOLVED",
            round(
                win_rate_resolved,
                2,
            ),
            "%",
        )


if __name__ == "__main__":
    main()
    part4_main()
