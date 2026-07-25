from datetime import datetime
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


if False and __name__ == "__main__":
    main()
    part4_main()


# =============================================================================
# PART 5 - ISOLATED PE REVERSAL EXPECTANCY RESEARCH
# =============================================================================

P5_HORIZONS = (5, 10, 15)
P5_TARGET = 0.10
P5_STOP = 0.15


def p5_simulate_short(entry, future, target_pct, stop_pct):
    """
    Bearish SPOT simulation.

    Target = spot falls below entry.
    Stop   = spot rises above entry.

    If target and stop are touched in the same candle,
    STOP is counted first (conservative assumption).

    If neither is touched, exit at final available candle close.
    """

    target_price = entry * (1.0 - target_pct / 100.0)
    stop_price = entry * (1.0 + stop_pct / 100.0)

    for candle in future:

        stop_hit = candle["h"] >= stop_price
        target_hit = candle["l"] <= target_price

        if stop_hit and target_hit:
            return "LOSS", -stop_pct

        if stop_hit:
            return "LOSS", -stop_pct

        if target_hit:
            return "WIN", target_pct

    # Time exit at final candle close.
    exit_price = future[-1]["c"]

    pnl_pct = (
        (entry - exit_price)
        / entry
        * 100.0
    )

    return "TIME_EXIT", pnl_pct


def part5_main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("\n" + "=" * 100)
    print("PART 5 - PE REVERSAL EXPECTANCY RESEARCH")
    print("SETUP: P4_BREAK_LOW_EMA_BEAR")
    print("ENTRY: NEXT-CANDLE BEARISH CONFIRMATION CLOSE")
    print("TARGET:", P5_TARGET, "%")
    print("STOP:", P5_STOP, "%")
    print("HORIZONS:", P5_HORIZONS)
    print("UNRESOLVED: TIME EXIT AT FINAL AVAILABLE CANDLE CLOSE")
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

    stats = {}

    for horizon in P5_HORIZONS:
        stats[horizon] = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "time_exits": 0,
            "positive_time_exits": 0,
            "negative_time_exits": 0,
            "flat_time_exits": 0,
            "total_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
        }

    raw_signals = 0
    confirmed_entries = 0

    for i, signal_candle in enumerate(candles):

        if i < 20:
            continue

        if i + 1 >= len(candles):
            continue

        confirm = candles[i + 1]

        # Never allow confirmation to cross trading day.
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

        # Exact Part-4 winning candidate.
        setup_ok = (
            f["PRIOR_UP_3"]
            and f["LOWER_HIGH"]
            and f["BEARISH"]
            and f["BREAK_PREV_LOW"]
            and f["EMA_BEAR"]
        )

        if not setup_ok:
            continue

        raw_signals += 1

        # Next-candle bearish confirmation.
        confirmed = (
            confirm["c"] < confirm["o"]
            and confirm["c"] < signal_candle["c"]
        )

        if not confirmed:
            continue

        entry = confirm["c"]

        confirmed_entries += 1

        for horizon in P5_HORIZONS:

            future = candles[
                i + 2:
                i + 2 + horizon
            ]

            # Never cross trading day.
            future = [
                x for x in future
                if (
                    x["dt"].date()
                    == signal_candle["dt"].date()
                )
            ]

            if not future:
                continue

            result, pnl_pct = p5_simulate_short(
                entry,
                future,
                P5_TARGET,
                P5_STOP,
            )

            st = stats[horizon]

            st["trades"] += 1
            st["total_pnl"] += pnl_pct

            if pnl_pct > 0:
                st["gross_profit"] += pnl_pct
            elif pnl_pct < 0:
                st["gross_loss"] += abs(pnl_pct)

            if result == "WIN":
                st["wins"] += 1

            elif result == "LOSS":
                st["losses"] += 1

            else:
                st["time_exits"] += 1

                if pnl_pct > 0:
                    st["positive_time_exits"] += 1

                elif pnl_pct < 0:
                    st["negative_time_exits"] += 1

                else:
                    st["flat_time_exits"] += 1

    print("CANDLES:", len(candles))
    print("RAW SETUP SIGNALS:", raw_signals)
    print("NEXT-CANDLE CONFIRMED ENTRIES:", confirmed_entries)

    print("\n" + "=" * 100)
    print("PART 5 FINAL EXPECTANCY RESULTS")
    print("=" * 100)

    for horizon in P5_HORIZONS:

        st = stats[horizon]

        trades = st["trades"]

        if not trades:
            continue

        win_rate = (
            st["wins"]
            / trades
            * 100.0
        )

        avg_pnl = (
            st["total_pnl"]
            / trades
        )

        profit_factor = (
            st["gross_profit"]
            / st["gross_loss"]
            if st["gross_loss"] > 0
            else float("inf")
        )

        print(
            "HORIZON",
            horizon,
            "| TRADES",
            trades,
            "| TARGET_WINS",
            st["wins"],
            "| SL_LOSSES",
            st["losses"],
            "| TIME_EXITS",
            st["time_exits"],
            "| TIME_POS",
            st["positive_time_exits"],
            "| TIME_NEG",
            st["negative_time_exits"],
            "| WIN_RATE_ALL",
            round(win_rate, 2),
            "%",
            "| AVG_PNL",
            round(avg_pnl, 4),
            "%",
            "| TOTAL_PNL",
            round(st["total_pnl"], 4),
            "%",
            "| PROFIT_FACTOR",
            round(profit_factor, 3),
        )


if False and __name__ == "__main__":
    part5_main()


# =============================================================================
# PART 6 - FRESH PE REVERSAL / ANTI-CHASE RESEARCH
# =============================================================================

P6_HORIZON = 5

P6_TARGETS = (
    0.08,
    0.10,
    0.12,
    0.15,
)

P6_STOPS = (
    0.10,
    0.15,
    0.20,
)

# Maximum bearish move already completed from
# signal candle OPEN to confirmation candle CLOSE.
#
# None = no anti-chase filter.
P6_MAX_EXTENSIONS = (
    None,
    0.05,
    0.10,
    0.15,
    0.20,
)


def p6_time_mode(dt):

    t = dt.time()

    if t < datetime.strptime(
        "11:00",
        "%H:%M",
    ).time():
        return "OPEN"

    if t < datetime.strptime(
        "13:00",
        "%H:%M",
    ).time():
        return "MID"

    if t < datetime.strptime(
        "14:30",
        "%H:%M",
    ).time():
        return "AFTERNOON"

    return "LATE"


def p6_simulate_short(
    entry,
    future,
    target_pct,
    stop_pct,
):

    target_price = (
        entry
        * (
            1.0
            - target_pct / 100.0
        )
    )

    stop_price = (
        entry
        * (
            1.0
            + stop_pct / 100.0
        )
    )

    for candle in future:

        stop_hit = (
            candle["h"]
            >= stop_price
        )

        target_hit = (
            candle["l"]
            <= target_price
        )

        # Conservative OHLC assumption.
        if stop_hit and target_hit:
            return "LOSS", -stop_pct

        if stop_hit:
            return "LOSS", -stop_pct

        if target_hit:
            return "WIN", target_pct

    # Neither target nor SL:
    # close trade at final horizon candle.
    exit_price = future[-1]["c"]

    pnl_pct = (
        (
            entry
            - exit_price
        )
        / entry
        * 100.0
    )

    return "TIME_EXIT", pnl_pct


def p6_new_stats():

    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "time_exits": 0,
        "time_pos": 0,
        "time_neg": 0,
        "total_pnl": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "extension_sum": 0.0,
    }


def part6_main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("\n" + "=" * 100)
    print("PART 6 - FRESH PE REVERSAL / ANTI-CHASE RESEARCH")
    print("SETUP: P4_BREAK_LOW_EMA_BEAR")
    print("ENTRY: NEXT-CANDLE BEARISH CONFIRMATION CLOSE")
    print("HORIZON:", P6_HORIZON, "CANDLES")
    print("ANTI-CHASE: SIGNAL OPEN -> CONFIRMATION CLOSE EXTENSION")
    print("EXTENSION FILTERS:", P6_MAX_EXTENSIONS)
    print("TARGETS:", P6_TARGETS)
    print("STOPS:", P6_STOPS)
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

    stats = defaultdict(
        p6_new_stats
    )

    raw_signals = 0
    confirmed_entries = 0

    extension_distribution = []

    for i, signal_candle in enumerate(candles):

        if i < 20:
            continue

        if i + 1 >= len(candles):
            continue

        confirm = candles[i + 1]

        # Confirmation cannot cross trading day.
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

        # Exact Part-5 setup.
        setup_ok = (
            f["PRIOR_UP_3"]
            and f["LOWER_HIGH"]
            and f["BEARISH"]
            and f["BREAK_PREV_LOW"]
            and f["EMA_BEAR"]
        )

        if not setup_ok:
            continue

        raw_signals += 1

        # Next candle confirmation.
        confirmed = (
            confirm["c"]
            < confirm["o"]
            and confirm["c"]
            < signal_candle["c"]
        )

        if not confirmed:
            continue

        entry = confirm["c"]

        confirmed_entries += 1

        # -------------------------------------------------------------
        # ANTI-CHASE MEASUREMENT
        #
        # Measures how much bearish movement has ALREADY happened
        # between signal candle OPEN and actual entry.
        #
        # Larger number = more move already consumed before entry.
        #
        # Uses only information available by entry time.
        # -------------------------------------------------------------

        if signal_candle["o"] <= 0:
            continue

        extension_pct = (
            (
                signal_candle["o"]
                - entry
            )
            / signal_candle["o"]
            * 100.0
        )

        # If price did not actually extend downward,
        # treat extension as zero.
        extension_pct = max(
            0.0,
            extension_pct,
        )

        extension_distribution.append(
            extension_pct
        )

        future = candles[
            i + 2:
            i + 2 + P6_HORIZON
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

        time_mode = p6_time_mode(
            signal_candle["dt"]
        )

        # Test BOTH individual time bucket
        # and all-session baseline.
        modes = (
            "ALL",
            time_mode,
        )

        for max_extension in P6_MAX_EXTENSIONS:

            if (
                max_extension is not None
                and extension_pct
                > max_extension
            ):
                continue

            extension_name = (
                "NO_FILTER"
                if max_extension is None
                else "MAX_EXT_" + str(max_extension)
            )

            for mode in modes:

                for target_pct in P6_TARGETS:

                    for stop_pct in P6_STOPS:

                        result, pnl_pct = (
                            p6_simulate_short(
                                entry,
                                future,
                                target_pct,
                                stop_pct,
                            )
                        )

                        key = (
                            extension_name,
                            mode,
                            target_pct,
                            stop_pct,
                        )

                        st = stats[key]

                        st["trades"] += 1
                        st["total_pnl"] += pnl_pct
                        st["extension_sum"] += (
                            extension_pct
                        )

                        if pnl_pct > 0:
                            st["gross_profit"] += (
                                pnl_pct
                            )

                        elif pnl_pct < 0:
                            st["gross_loss"] += abs(
                                pnl_pct
                            )

                        if result == "WIN":
                            st["wins"] += 1

                        elif result == "LOSS":
                            st["losses"] += 1

                        else:
                            st["time_exits"] += 1

                            if pnl_pct > 0:
                                st["time_pos"] += 1

                            elif pnl_pct < 0:
                                st["time_neg"] += 1

    print(
        "CANDLES:",
        len(candles),
    )

    print(
        "RAW SETUP SIGNALS:",
        raw_signals,
    )

    print(
        "NEXT-CANDLE CONFIRMED:",
        confirmed_entries,
    )

    if extension_distribution:

        sorted_ext = sorted(
            extension_distribution
        )

        n = len(sorted_ext)

        print(
            "EXTENSION AVG:",
            round(
                sum(sorted_ext) / n,
                4,
            ),
            "%",
        )

        print(
            "EXTENSION MEDIAN:",
            round(
                sorted_ext[n // 2],
                4,
            ),
            "%",
        )

        print(
            "EXTENSION MAX:",
            round(
                max(sorted_ext),
                4,
            ),
            "%",
        )

    print("\n" + "=" * 100)
    print("PART 6 FINAL ANTI-CHASE RESULTS")
    print("=" * 100)

    results = []

    for (
        extension_name,
        mode,
        target_pct,
        stop_pct,
    ), st in stats.items():

        trades = st["trades"]

        if not trades:
            continue

        avg_pnl = (
            st["total_pnl"]
            / trades
        )

        profit_factor = (
            st["gross_profit"]
            / st["gross_loss"]
            if st["gross_loss"] > 0
            else float("inf")
        )

        win_rate = (
            st["wins"]
            / trades
            * 100.0
        )

        avg_extension = (
            st["extension_sum"]
            / trades
        )

        results.append(
            (
                profit_factor,
                avg_pnl,
                trades,
                extension_name,
                mode,
                target_pct,
                stop_pct,
                st["wins"],
                st["losses"],
                st["time_exits"],
                st["time_pos"],
                st["time_neg"],
                win_rate,
                st["total_pnl"],
                avg_extension,
            )
        )

    # Primary ranking:
    # Profit Factor first, then expectancy.
    results.sort(
        reverse=True
    )

    for (
        profit_factor,
        avg_pnl,
        trades,
        extension_name,
        mode,
        target_pct,
        stop_pct,
        wins,
        losses,
        time_exits,
        time_pos,
        time_neg,
        win_rate,
        total_pnl,
        avg_extension,
    ) in results:

        print(
            extension_name,
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
            "| TIME_EXIT",
            time_exits,
            "| TIME_POS",
            time_pos,
            "| TIME_NEG",
            time_neg,
            "| WIN_RATE",
            round(win_rate, 2),
            "%",
            "| AVG_PNL",
            round(avg_pnl, 4),
            "%",
            "| TOTAL_PNL",
            round(total_pnl, 4),
            "%",
            "| PF",
            round(profit_factor, 3),
            "| AVG_EXT",
            round(avg_extension, 4),
            "%",
        )


# Part 6 main disabled for Part 7 research
# if __name__ == "__main__":
#     part6_main()

# =============================================================================
# PART 7 - STRICT FRESH ENTRY / ANTI-CHASE RESEARCH
# Goal:
#   Do NOT signal after the bearish move has already substantially happened.
#
# Filters use ONLY information available at confirmation candle close:
#   1. Signal-open -> confirmation-close maximum extension
#   2. Confirmation candle bearish body size
#
# No look-ahead is used for entry filters.
# =============================================================================

P7_HORIZON = 5

P7_TARGETS = (
    0.08,
    0.10,
    0.12,
)

P7_STOPS = (
    0.10,
    0.15,
    0.20,
)

# Maximum move already completed before entry.
P7_MAX_EXTENSIONS = (
    0.06,
    0.08,
    0.10,
    0.12,
)

# Maximum bearish body of confirmation candle.
# None = extension-only baseline.
P7_MAX_CONFIRM_BODIES = (
    None,
    0.05,
    0.08,
    0.10,
)


def p7_new_stats():
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "time_exits": 0,
        "time_pos": 0,
        "time_neg": 0,
        "total_pnl": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "extension_sum": 0.0,
        "confirm_body_sum": 0.0,
    }


def part7_main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("\n" + "=" * 110)
    print("PART 7 - STRICT FRESH PE REVERSAL / MOVE-ALREADY-GONE FILTER")
    print("SETUP: P4_BREAK_LOW_EMA_BEAR")
    print("ENTRY: NEXT-CANDLE BEARISH CONFIRMATION CLOSE")
    print("HORIZON:", P7_HORIZON, "CANDLES")
    print("MAX EXTENSIONS:", P7_MAX_EXTENSIONS)
    print("MAX CONFIRM BODIES:", P7_MAX_CONFIRM_BODIES)
    print("TARGETS:", P7_TARGETS)
    print("STOPS:", P7_STOPS)
    print("RULE: OVER-EXTENDED OR IMPULSIVE CONFIRMATION = NO SIGNAL")
    print("=" * 110)

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
        p7_new_stats
    )

    raw_signals = 0
    confirmed_entries = 0

    for i, signal_candle in enumerate(candles):

        if i < 20:
            continue

        if i + 1 >= len(candles):
            continue

        confirm = candles[i + 1]

        # Never confirm using next trading day's candle.
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

        # Exact Part 5 / Part 6 base setup.
        setup_ok = (
            f["PRIOR_UP_3"]
            and f["LOWER_HIGH"]
            and f["BEARISH"]
            and f["BREAK_PREV_LOW"]
            and f["EMA_BEAR"]
        )

        if not setup_ok:
            continue

        raw_signals += 1

        # Realistic next-candle bearish confirmation.
        confirmed = (
            confirm["c"] < confirm["o"]
            and confirm["c"] < signal_candle["c"]
        )

        if not confirmed:
            continue

        entry = confirm["c"]

        if (
            signal_candle["o"] <= 0
            or confirm["o"] <= 0
        ):
            continue

        confirmed_entries += 1

        # ---------------------------------------------------------
        # FILTER 1: TOTAL MOVE ALREADY COMPLETED BEFORE ENTRY
        #
        # Signal candle OPEN -> confirmation candle CLOSE.
        # If this is too large, PE move is considered already gone.
        # ---------------------------------------------------------

        extension_pct = (
            (
                signal_candle["o"]
                - entry
            )
            / signal_candle["o"]
            * 100.0
        )

        extension_pct = max(
            0.0,
            extension_pct,
        )

        # ---------------------------------------------------------
        # FILTER 2: CONFIRMATION CANDLE IMPULSE
        #
        # A very large bearish confirmation candle can mean that
        # confirmation arrived only after the immediate move.
        # ---------------------------------------------------------

        confirm_body_pct = (
            (
                confirm["o"]
                - confirm["c"]
            )
            / confirm["o"]
            * 100.0
        )

        confirm_body_pct = max(
            0.0,
            confirm_body_pct,
        )

        future = candles[
            i + 2:
            i + 2 + P7_HORIZON
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

        time_mode = p6_time_mode(
            signal_candle["dt"]
        )

        modes = (
            "ALL",
            time_mode,
        )

        for max_extension in P7_MAX_EXTENSIONS:

            # STRICT MOVE-ALREADY-GONE REJECTION.
            if extension_pct > max_extension:
                continue

            for max_body in P7_MAX_CONFIRM_BODIES:

                # None gives extension-only baseline.
                if (
                    max_body is not None
                    and confirm_body_pct > max_body
                ):
                    continue

                body_name = (
                    "BODY_ANY"
                    if max_body is None
                    else "MAX_BODY_" + str(max_body)
                )

                extension_name = (
                    "MAX_EXT_"
                    + str(max_extension)
                )

                for mode in modes:

                    for target_pct in P7_TARGETS:

                        for stop_pct in P7_STOPS:

                            result, pnl_pct = (
                                p6_simulate_short(
                                    entry,
                                    future,
                                    target_pct,
                                    stop_pct,
                                )
                            )

                            key = (
                                extension_name,
                                body_name,
                                mode,
                                target_pct,
                                stop_pct,
                            )

                            st = stats[key]

                            st["trades"] += 1
                            st["total_pnl"] += pnl_pct
                            st["extension_sum"] += extension_pct
                            st["confirm_body_sum"] += confirm_body_pct

                            if pnl_pct > 0:
                                st["gross_profit"] += pnl_pct

                            elif pnl_pct < 0:
                                st["gross_loss"] += abs(
                                    pnl_pct
                                )

                            if result == "WIN":
                                st["wins"] += 1

                            elif result == "LOSS":
                                st["losses"] += 1

                            else:
                                st["time_exits"] += 1

                                if pnl_pct > 0:
                                    st["time_pos"] += 1
                                elif pnl_pct < 0:
                                    st["time_neg"] += 1

    print("CANDLES:", len(candles))
    print("RAW SETUP SIGNALS:", raw_signals)
    print(
        "NEXT-CANDLE CONFIRMED ENTRIES:",
        confirmed_entries,
    )

    print("\n" + "=" * 110)
    print("PART 7 FINAL STRICT ANTI-CHASE RESULTS")
    print("=" * 110)

    results = []

    for key, st in stats.items():

        (
            extension_name,
            body_name,
            mode,
            target_pct,
            stop_pct,
        ) = key

        trades = st["trades"]

        if not trades:
            continue

        win_rate = (
            st["wins"]
            / trades
            * 100.0
        )

        avg_pnl = (
            st["total_pnl"]
            / trades
        )

        avg_extension = (
            st["extension_sum"]
            / trades
        )

        avg_body = (
            st["confirm_body_sum"]
            / trades
        )

        if st["gross_loss"] > 0:
            profit_factor = (
                st["gross_profit"]
                / st["gross_loss"]
            )
        elif st["gross_profit"] > 0:
            profit_factor = 999.0
        else:
            profit_factor = 0.0

        results.append(
            (
                avg_pnl,
                profit_factor,
                trades,
                win_rate,
                extension_name,
                body_name,
                mode,
                target_pct,
                stop_pct,
                st,
                avg_extension,
                avg_body,
            )
        )

    # Primary ranking = expectancy per trade.
    # Secondary ranking = profit factor.
    results.sort(
        key=lambda x: (
            x[0],
            x[1],
            x[2],
        ),
        reverse=True,
    )

    for (
        avg_pnl,
        profit_factor,
        trades,
        win_rate,
        extension_name,
        body_name,
        mode,
        target_pct,
        stop_pct,
        st,
        avg_extension,
        avg_body,
    ) in results:

        print(
            extension_name,
            "|",
            body_name,
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
            st["wins"],
            "| LOSSES",
            st["losses"],
            "| TIME_EXIT",
            st["time_exits"],
            "| TIME_POS",
            st["time_pos"],
            "| TIME_NEG",
            st["time_neg"],
            "| WIN_RATE",
            round(win_rate, 2),
            "%",
            "| AVG_PNL",
            round(avg_pnl, 4),
            "%",
            "| TOTAL_PNL",
            round(st["total_pnl"], 4),
            "%",
            "| PF",
            round(profit_factor, 3),
            "| AVG_EXT",
            round(avg_extension, 4),
            "%",
            "| AVG_BODY",
            round(avg_body, 4),
            "%",
        )




if __name__ == "__main__":
    pass
    # part7_main()  # disabled for Part 8 research

# ============================================================
# PART 8 - EMA MARKET REGIME / CONTEXT RESEARCH
# ============================================================

P8_HORIZON = 5
P8_TARGETS = (0.08, 0.10, 0.12)
P8_STOPS = (0.10, 0.15, 0.20)

P8_EMA_GAPS = (
    None,
    0.01,
    0.02,
    0.03,
    0.05,
)


def p8_new_stats():
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "time_exits": 0,
        "time_pos": 0,
        "time_neg": 0,
        "total_pnl": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "ema_gap_sum": 0.0,
    }


def part8_main():
    token = open(TOKEN_FILE).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("\n" + "=" * 110)
    print("PART 8 - PE REVERSAL EMA MARKET REGIME RESEARCH")
    print("BASE SETUP: P4_BREAK_LOW_EMA_BEAR")
    print("ENTRY: NEXT-CANDLE BEARISH CONFIRMATION CLOSE")
    print("HORIZON:", P8_HORIZON, "CANDLES")
    print("EMA GAP FILTERS:", P8_EMA_GAPS)
    print("CONTEXT: EMA9 BELOW EMA20 + EMA20 SLOPE")
    print("TARGETS:", P8_TARGETS)
    print("STOPS:", P8_STOPS)
    print("=" * 110)

    rows = fetch_spot_history(m)

    candles = [
        parse(row)
        for row in rows
    ]

    candles = [
        x for x in candles
        if x
    ]

    stats = defaultdict(p8_new_stats)

    raw_signals = 0
    confirmed_entries = 0

    for i, signal_candle in enumerate(candles):

        if i < 25:
            continue

        if i + 1 >= len(candles):
            continue

        confirm = candles[i + 1]

        if (
            confirm["dt"].date()
            != signal_candle["dt"].date()
        ):
            continue

        closes = [
            x["c"]
            for x in candles[i - 25:i + 1]
        ]

        ema9 = ema(closes, 9)
        ema20 = ema(closes, 20)

        previous_closes = [
            x["c"]
            for x in candles[i - 25:i]
        ]

        prev_ema20 = ema(
            previous_closes,
            20,
        )

        if (
            ema9 is None
            or ema20 is None
            or prev_ema20 is None
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

        setup_ok = (
            f["PRIOR_UP_3"]
            and f["LOWER_HIGH"]
            and f["BEARISH"]
            and f["BREAK_PREV_LOW"]
            and f["EMA_BEAR"]
        )

        if not setup_ok:
            continue

        raw_signals += 1

        confirmed = (
            confirm["c"] < confirm["o"]
            and confirm["c"] < signal_candle["c"]
        )

        if not confirmed:
            continue

        entry = confirm["c"]

        if entry <= 0 or ema20 <= 0:
            continue

        confirmed_entries += 1

        # EMA9-EMA20 bearish separation as percentage
        ema_gap_pct = (
            (ema20 - ema9)
            / ema20
            * 100.0
        )

        # EMA20 slope at signal candle
        ema20_falling = (
            ema20 < prev_ema20
        )

        slope_mode = (
            "EMA20_FALLING"
            if ema20_falling
            else "EMA20_NOT_FALLING"
        )

        future = candles[
            i + 2:
            i + 2 + P8_HORIZON
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

        time_mode = p6_time_mode(
            signal_candle["dt"]
        )

        modes = (
            "ALL",
            time_mode,
        )

        for min_gap in P8_EMA_GAPS:

            if (
                min_gap is not None
                and ema_gap_pct < min_gap
            ):
                continue

            gap_name = (
                "GAP_ANY"
                if min_gap is None
                else "MIN_GAP_" + str(min_gap)
            )

            slope_modes = (
                "SLOPE_ANY",
                slope_mode,
            )

            for slope_name in slope_modes:

                for mode in modes:

                    for target_pct in P8_TARGETS:

                        for stop_pct in P8_STOPS:

                            result, pnl_pct = (
                                p6_simulate_short(
                                    entry,
                                    future,
                                    target_pct,
                                    stop_pct,
                                )
                            )

                            key = (
                                gap_name,
                                slope_name,
                                mode,
                                target_pct,
                                stop_pct,
                            )

                            st = stats[key]

                            st["trades"] += 1
                            st["total_pnl"] += pnl_pct
                            st["ema_gap_sum"] += ema_gap_pct

                            if pnl_pct > 0:
                                st["gross_profit"] += pnl_pct
                            elif pnl_pct < 0:
                                st["gross_loss"] += abs(pnl_pct)

                            if result == "WIN":
                                st["wins"] += 1
                            elif result == "LOSS":
                                st["losses"] += 1
                            else:
                                st["time_exits"] += 1

                                if pnl_pct > 0:
                                    st["time_pos"] += 1
                                elif pnl_pct < 0:
                                    st["time_neg"] += 1

    print("CANDLES:", len(candles))
    print("RAW SETUP SIGNALS:", raw_signals)
    print(
        "NEXT-CANDLE CONFIRMED ENTRIES:",
        confirmed_entries,
    )

    print("\n" + "=" * 110)
    print("PART 8 FINAL EMA REGIME RESULTS")
    print("=" * 110)

    results = []

    for key, st in stats.items():

        (
            gap_name,
            slope_name,
            mode,
            target_pct,
            stop_pct,
        ) = key

        trades = st["trades"]

        if not trades:
            continue

        win_rate = (
            st["wins"]
            / trades
            * 100.0
        )

        avg_pnl = (
            st["total_pnl"]
            / trades
        )

        avg_gap = (
            st["ema_gap_sum"]
            / trades
        )

        if st["gross_loss"] > 0:
            profit_factor = (
                st["gross_profit"]
                / st["gross_loss"]
            )
        elif st["gross_profit"] > 0:
            profit_factor = 999.0
        else:
            profit_factor = 0.0

        results.append(
            (
                avg_pnl,
                profit_factor,
                trades,
                win_rate,
                gap_name,
                slope_name,
                mode,
                target_pct,
                stop_pct,
                st,
                avg_gap,
            )
        )

    results.sort(
        key=lambda x: (
            x[0],
            x[1],
            x[2],
        ),
        reverse=True,
    )

    for (
        avg_pnl,
        profit_factor,
        trades,
        win_rate,
        gap_name,
        slope_name,
        mode,
        target_pct,
        stop_pct,
        st,
        avg_gap,
    ) in results:

        print(
            gap_name,
            "|",
            slope_name,
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
            st["wins"],
            "| LOSSES",
            st["losses"],
            "| TIME_EXIT",
            st["time_exits"],
            "| TIME_POS",
            st["time_pos"],
            "| TIME_NEG",
            st["time_neg"],
            "| WIN_RATE",
            round(win_rate, 2),
            "%",
            "| AVG_PNL",
            round(avg_pnl, 4),
            "%",
            "| TOTAL_PNL",
            round(st["total_pnl"], 4),
            "%",
            "| PF",
            round(profit_factor, 3),
            "| AVG_EMA_GAP",
            round(avg_gap, 4),
            "%",
        )


if __name__ == "__main__":
    pass


# ============================================================
# PART 10 - ATR / VOLATILITY REGIME RESEARCH
# ============================================================

P10_HORIZON = 5
P10_ATR_PERIOD = 14

P10_TARGETS = (
    0.08,
    0.10,
    0.12,
)

P10_STOPS = (
    0.10,
    0.15,
    0.20,
)

# Minimum normalized ATR percentage.
# None = no ATR% filter baseline.
P10_MIN_ATR_PCTS = (
    None,
    0.05,
    0.08,
    0.10,
    0.12,
    0.15,
    0.20,
)

# Current ATR / average of previous ATR values.
# None = no expansion filter.
P10_MIN_ATR_EXPANSIONS = (
    None,
    1.00,
    1.05,
    1.10,
    1.20,
)

# Signal candle range / current ATR.
# None = no range-expansion filter.
P10_MIN_RANGE_ATR = (
    None,
    0.50,
    0.75,
    1.00,
    1.25,
    1.50,
)


def p10_true_range(candle, prev_close):
    return max(
        candle["h"] - candle["l"],
        abs(candle["h"] - prev_close),
        abs(candle["l"] - prev_close),
    )


def p10_atr_series(candles, period=14):
    """
    Wilder ATR.
    Returns list aligned with candles.
    Values before enough history are None.
    """
    result = [None] * len(candles)

    if len(candles) <= period:
        return result

    trs = [None]

    for i in range(1, len(candles)):
        trs.append(
            p10_true_range(
                candles[i],
                candles[i - 1]["c"],
            )
        )

    first_values = [
        x for x in trs[1:period + 1]
        if x is not None
    ]

    if len(first_values) < period:
        return result

    atr_value = sum(first_values) / period
    result[period] = atr_value

    for i in range(period + 1, len(candles)):
        atr_value = (
            (atr_value * (period - 1))
            + trs[i]
        ) / period

        result[i] = atr_value

    return result


def p10_time_mode(dt):
    t = dt.time()

    if t.hour < 11:
        return "OPEN"

    if t.hour < 13:
        return "MID"

    return "AFTERNOON"


def p10_new_stats():
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "time_exits": 0,
        "time_pos": 0,
        "time_neg": 0,
        "total_pnl": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "atr_pct_sum": 0.0,
        "atr_expansion_sum": 0.0,
        "range_atr_sum": 0.0,
    }


# PART 13 - CHRONOLOGICAL OUT-OF-SAMPLE VALIDATION
# First 70% of trading days = in-sample research/training.
# Last 30% of trading days = untouched out-of-sample validation.
P13_TRAIN_RATIO = 0.70


def part10_main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("\n" + "=" * 120)
    print("PART 10 - ATR / VOLATILITY REGIME RESEARCH")
    print("BASE SETUP: P4_BREAK_LOW_EMA_BEAR")
    print("ENTRY: NEXT-CANDLE BEARISH CONFIRMATION CLOSE")
    print("ATR PERIOD:", P10_ATR_PERIOD)
    print("HORIZON:", P10_HORIZON, "CANDLES")
    print("TARGETS:", P10_TARGETS)
    print("STOPS:", P10_STOPS)
    print("TEST: ATR% + ATR EXPANSION + SIGNAL RANGE/ATR + TIME REGIME")
    print("=" * 120)

    rows = fetch_spot_history(m)

    candles = [
        parse(row)
        for row in rows
    ]

    candles = [
        x for x in candles
        if x
    ]

    print("CANDLES:", len(candles))

    atr_values = p10_atr_series(
        candles,
        P10_ATR_PERIOD,
    )

    stats = defaultdict(
        p10_new_stats
    )

    # PART 13: Chronological train / untouched OOS split.
    trading_days = sorted(
        set(x["dt"].date() for x in candles)
    )
    split_idx = int(
        len(trading_days) * P13_TRAIN_RATIO
    )
    train_days = set(
        trading_days[:split_idx]
    )
    oos_days = set(
        trading_days[split_idx:]
    )

    train_stats = defaultdict(
        p10_new_stats
    )
    oos_stats = defaultdict(
        p10_new_stats
    )

    print(
        "PART13 TRAIN:",
        len(train_days),
        "DAYS",
        min(train_days),
        "TO",
        max(train_days),
    )
    print(
        "PART13 OOS:",
        len(oos_days),
        "DAYS",
        min(oos_days),
        "TO",
        max(oos_days),
    )

    raw_signals = 0
    confirmed_entries = 0
    valid_atr_entries = 0
    p14_unique_events = {"TRAIN": [], "OOS": []}
    p15_trade_events = {"TRAIN": [], "OOS": []}



    for i, signal_candle in enumerate(candles):

        if i < 30:
            continue

        if i + 1 >= len(candles):
            continue

        confirm = candles[i + 1]

        # Do not use next trading day's candle.
        if (
            confirm["dt"].date()
            != signal_candle["dt"].date()
        ):
            continue

        closes = [
            x["c"]
            for x in candles[i - 20:i + 1]
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

        # PART 12:
        # Compare higher-frequency P4_BASE against the
        # stricter P4_BREAK_LOW_EMA_BEAR quality baseline.
        setups = {
            "P4_BASE": (
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
            ),
            "P4_BREAK_LOW_EMA_BEAR": (
                f["PRIOR_UP_3"]
                and f["LOWER_HIGH"]
                and f["BEARISH"]
                and f["BREAK_PREV_LOW"]
                and f["EMA_BEAR"]
            ),
        }

        active_setups = [
            name
            for name, ok in setups.items()
            if ok
        ]

        if not active_setups:
            continue

        raw_signals += 1

        # Realistic next-candle confirmation.
        confirmed = (
            confirm["c"] < confirm["o"]
            and confirm["c"] < signal_candle["c"]
        )

        if not confirmed:
            continue

        confirmed_entries += 1

        entry = confirm["c"]

        if entry <= 0:
            continue

        current_atr = atr_values[i]

        if (
            current_atr is None
            or current_atr <= 0
        ):
            continue

        valid_atr_entries += 1

        # Normalized ATR as percentage of signal close.
        atr_pct = (
            current_atr
            / signal_candle["c"]
            * 100.0
        )

        # ATR expansion:
        # current ATR divided by average ATR of previous 5 valid bars.
        previous_atrs = [
            atr_values[j]
            for j in range(
                max(P10_ATR_PERIOD, i - 5),
                i,
            )
            if (
                atr_values[j] is not None
                and atr_values[j] > 0
            )
        ]

        if previous_atrs:
            previous_atr_avg = (
                sum(previous_atrs)
                / len(previous_atrs)
            )

            atr_expansion = (
                current_atr
                / previous_atr_avg
            )
        else:
            atr_expansion = 1.0

        signal_range = (
            signal_candle["h"]
            - signal_candle["l"]
        )

        range_atr = (
            signal_range
            / current_atr
        )

        trade_day = signal_candle["dt"].date()
        if trade_day in train_days:
            p14_split = "TRAIN"
        elif trade_day in oos_days:
            p14_split = "OOS"
        else:
            p14_split = None

        if p14_split is not None:
            p14_unique_events[p14_split].append({
                "dt": signal_candle["dt"],
                "atr_pct": atr_pct,
                "atr_expansion": atr_expansion,
                "range_atr": range_atr,
                "time_mode": p10_time_mode(signal_candle["dt"]),
            })


        future = candles[
            i + 2:
            i + 2 + P10_HORIZON
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

        if p14_split is not None:
            p15_trade_events[p14_split].append({
                "dt": signal_candle["dt"],
                "entry": entry,
                "future": future,
                "atr_pct": atr_pct,
                "atr_expansion": atr_expansion,
                "range_atr": range_atr,
                "time_mode": p10_time_mode(signal_candle["dt"]),
                "setups": tuple(active_setups),
            })


        time_mode = p10_time_mode(
            signal_candle["dt"]
        )

        modes = (
            "ALL",
            time_mode,
        )

        for min_atr_pct in P10_MIN_ATR_PCTS:

            if (
                min_atr_pct is not None
                and atr_pct < min_atr_pct
            ):
                continue

            atr_name = (
                "ATR_ANY"
                if min_atr_pct is None
                else "MIN_ATR_" + str(min_atr_pct)
            )

            for min_atr_expansion in P10_MIN_ATR_EXPANSIONS:

                if (
                    min_atr_expansion is not None
                    and atr_expansion < min_atr_expansion
                ):
                    continue

                expansion_name = (
                    "EXP_ANY"
                    if min_atr_expansion is None
                    else "MIN_EXP_" + str(min_atr_expansion)
                )

                for min_range_atr in P10_MIN_RANGE_ATR:

                    if (
                        min_range_atr is not None
                        and range_atr < min_range_atr
                    ):
                        continue

                    range_name = (
                        "RANGE_ANY"
                        if min_range_atr is None
                        else "MIN_RANGE_ATR_" + str(min_range_atr)
                    )

                    for mode in modes:

                        for target_pct in P10_TARGETS:

                            for stop_pct in P10_STOPS:

                                result, pnl_pct = (
                                    p6_simulate_short(
                                        entry,
                                        future,
                                        target_pct,
                                        stop_pct,
                                    )
                                )

                                for setup_name in active_setups:
                                    key = (
                                        setup_name,
                                        atr_name,
                                        expansion_name,
                                        range_name,
                                        mode,
                                        target_pct,
                                        stop_pct,
                                    )

                                    st = stats[key]

                                    # PART 13:
                                    # Record the identical trade independently
                                    # in TRAIN or untouched OOS statistics.
                                    trade_day = signal_candle["dt"].date()

                                    if trade_day in train_days:
                                        split_st = train_stats[key]
                                    elif trade_day in oos_days:
                                        split_st = oos_stats[key]
                                    else:
                                        split_st = None

                                    st["trades"] += 1
                                    st["total_pnl"] += pnl_pct

                                    st["atr_pct_sum"] += atr_pct
                                    st["atr_expansion_sum"] += atr_expansion
                                    st["range_atr_sum"] += range_atr

                                    if pnl_pct > 0:
                                        st["gross_profit"] += pnl_pct

                                    elif pnl_pct < 0:
                                        st["gross_loss"] += abs(
                                            pnl_pct
                                        )

                                    if result == "WIN":
                                        st["wins"] += 1

                                    elif result == "LOSS":
                                        st["losses"] += 1

                                    else:
                                        st["time_exits"] += 1

                                        if pnl_pct > 0:
                                            st["time_pos"] += 1

                                        elif pnl_pct < 0:
                                            st["time_neg"] += 1

                                    if split_st is not None:
                                        split_st["trades"] += 1
                                        split_st["total_pnl"] += pnl_pct
                                        split_st["atr_pct_sum"] += atr_pct
                                        split_st["atr_expansion_sum"] += atr_expansion
                                        split_st["range_atr_sum"] += range_atr

                                        if pnl_pct > 0:
                                            split_st["gross_profit"] += pnl_pct
                                        elif pnl_pct < 0:
                                            split_st["gross_loss"] += abs(pnl_pct)

                                        if result == "WIN":
                                            split_st["wins"] += 1
                                        elif result == "LOSS":
                                            split_st["losses"] += 1
                                        else:
                                            split_st["time_exits"] += 1

                                            if pnl_pct > 0:
                                                split_st["time_pos"] += 1
                                            elif pnl_pct < 0:
                                                split_st["time_neg"] += 1

    print("RAW SETUP SIGNALS:", raw_signals)
    print(
        "NEXT-CANDLE CONFIRMED ENTRIES:",
        confirmed_entries,
    )
    print(
        "VALID ATR ENTRIES:",
        valid_atr_entries,
    )

    results = []

    for key, st in stats.items():

        trades = st["trades"]

        if not trades:
            continue

        (
            setup_name,
            atr_name,
            expansion_name,
            range_name,
            mode,
            target_pct,
            stop_pct,
        ) = key

        win_rate = (
            st["wins"]
            / trades
            * 100.0
        )

        avg_pnl = (
            st["total_pnl"]
            / trades
        )

        if st["gross_loss"] > 0:
            profit_factor = (
                st["gross_profit"]
                / st["gross_loss"]
            )

        elif st["gross_profit"] > 0:
            profit_factor = 999.0

        else:
            profit_factor = 0.0

        avg_atr_pct = (
            st["atr_pct_sum"]
            / trades
        )

        avg_atr_expansion = (
            st["atr_expansion_sum"]
            / trades
        )

        avg_range_atr = (
            st["range_atr_sum"]
            / trades
        )

        results.append(
            (
                avg_pnl,
                profit_factor,
                trades,
                win_rate,
                setup_name,
                atr_name,
                expansion_name,
                range_name,
                mode,
                target_pct,
                stop_pct,
                st,
                avg_atr_pct,
                avg_atr_expansion,
                avg_range_atr,
            )
        )

    # Rank primarily by expectancy,
    # then PF, then sample size.
    results.sort(
        key=lambda x: (
            x[0],
            x[1],
            x[2],
        ),
        reverse=True,
    )

    # PART 11: Frequency vs quality analysis.
    trading_days = len(set(x["dt"].date() for x in candles))
    trading_month_factor = 21.0

    def p11_frequency_row(x):
        (
            avg_pnl,
            profit_factor,
            trades,
            win_rate,
            setup_name,
            atr_name,
            expansion_name,
            range_name,
            mode,
            target_pct,
            stop_pct,
            st,
            avg_atr_pct,
            avg_atr_expansion,
            avg_range_atr,
        ) = x

        trades_per_day = trades / trading_days if trading_days else 0.0
        trades_per_month = trades_per_day * trading_month_factor

        return {
            "row": x,
            "trades": trades,
            "trades_per_day": trades_per_day,
            "trades_per_month": trades_per_month,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "pf": profit_factor,
            "setup": setup_name,
            "atr": atr_name,
            "exp": expansion_name,
            "range": range_name,
            "mode": mode,
            "target": target_pct,
            "stop": stop_pct,
        }

    p11_rows = [p11_frequency_row(x) for x in results]

    # Avoid tiny samples and pathological infinite-like PF values.
    eligible = [
        r for r in p11_rows
        if r["trades"] >= 20
        and r["avg_pnl"] > 0
        and r["pf"] >= 1.20
        and r["pf"] < 900
    ]

    high_quality = sorted(
        eligible,
        key=lambda r: (
            r["avg_pnl"],
            r["pf"],
            r["win_rate"],
            r["trades"],
        ),
        reverse=True,
    )

    balanced = sorted(
        eligible,
        key=lambda r: (
            r["avg_pnl"] * min(r["pf"], 5.0) * (r["trades_per_day"] ** 0.5),
            r["trades"],
        ),
        reverse=True,
    )

    high_frequency = sorted(
        [
            r for r in eligible
            if r["win_rate"] >= 50.0
            and r["pf"] >= 1.25
        ],
        key=lambda r: (
            r["trades_per_day"],
            r["avg_pnl"],
            r["pf"],
        ),
        reverse=True,
    )

    def p11_print_bucket(title, bucket, limit=10):
        print("\n" + "=" * 120)
        print(title)
        print("=" * 120)

        for rank, r in enumerate(bucket[:limit], 1):
            print(
                "RANK", rank,
                "| SETUP", r["setup"],
                "|", r["atr"],
                "|", r["exp"],
                "|", r["range"],
                "|", r["mode"],
                "| TARGET", r["target"], "%",
                "| SL", r["stop"], "%",
                "| TRADES", r["trades"],
                "| TRADES/DAY", round(r["trades_per_day"], 3),
                "| TRADES/MONTH", round(r["trades_per_month"], 1),
                "| WIN_RATE", round(r["win_rate"], 2), "%",
                "| AVG_PNL", round(r["avg_pnl"], 4), "%",
                "| PF", round(r["pf"], 3),
            )

    print("\n" + "=" * 120)
    print("PART 11 - FREQUENCY VS QUALITY OPTIMIZER")
    print("TRADING DAYS:", trading_days)
    print("MAX CONFIRMED BASE ENTRIES:", confirmed_entries)
    if trading_days:
        print(
            "MAX BASE SIGNAL FREQUENCY:",
            round(confirmed_entries / trading_days, 3),
            "TRADES/DAY",
        )
    print("=" * 120)

    p11_print_bucket(
        "PART 11 HIGH QUALITY - EXPECTANCY FIRST",
        high_quality,
    )
    p11_print_bucket(
        "PART 11 BALANCED - QUALITY X FREQUENCY",
        balanced,
    )
    p11_print_bucket(
        "PART 11 HIGH FREQUENCY - PROFITABLE FILTERS",
        high_frequency,
    )

    print("\n" + "=" * 120)
    print("PART 11 FREQUENCY VS QUALITY RESULTS")
    print("RANKING: AVG_PNL -> PF -> TRADES")
    print("MINIMUM 20 TRADES SHOWN")
    print("=" * 120)

    shown = 0

    for (
        avg_pnl,
        profit_factor,
        trades,
        win_rate,
        setup_name,
        atr_name,
        expansion_name,
        range_name,
        mode,
        target_pct,
        stop_pct,
        st,
        avg_atr_pct,
        avg_atr_expansion,
        avg_range_atr,
    ) in results:

        if trades < 20:
            continue

        print(
            "SETUP",
            setup_name,
            "|",
            atr_name,
            "|",
            expansion_name,
            "|",
            range_name,
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
            st["wins"],
            "| LOSSES",
            st["losses"],
            "| TIME_EXIT",
            st["time_exits"],
            "| WIN_RATE",
            round(win_rate, 2),
            "%",
            "| AVG_PNL",
            round(avg_pnl, 4),
            "%",
            "| TOTAL_PNL",
            round(st["total_pnl"], 4),
            "%",
            "| PF",
            round(profit_factor, 3),
            "| AVG_ATR",
            round(avg_atr_pct, 4),
            "%",
            "| AVG_EXP",
            round(avg_atr_expansion, 3),
            "| AVG_RANGE_ATR",
            round(avg_range_atr, 3),
        )

        shown += 1

        # Keep terminal output manageable.
        if shown >= 100:
            break

    print("\n" + "=" * 120)
    print("PART 11 BASELINE COMPARISON")
    print("=" * 120)

    baseline_results = [
        x for x in results
        if (
            x[4] == "ATR_ANY"
            and x[5] == "EXP_ANY"
            and x[6] == "RANGE_ANY"
            and x[7] == "ALL"
        )
    ]

    for x in baseline_results:
        (
            avg_pnl,
            profit_factor,
            trades,
            win_rate,
            atr_name,
            expansion_name,
            range_name,
            mode,
            target_pct,
            stop_pct,
            st,
            avg_atr_pct,
            avg_atr_expansion,
            avg_range_atr,
        ) = x

        print(
            "BASELINE",
            "| TARGET",
            target_pct,
            "%",
            "| SL",
            stop_pct,
            "%",
            "| TRADES",
            trades,
            "| WIN_RATE",
            round(win_rate, 2),
            "%",
            "| AVG_PNL",
            round(avg_pnl, 4),
            "%",
            "| TOTAL_PNL",
            round(st["total_pnl"], 4),
            "%",
            "| PF",
            round(profit_factor, 3),
        )

    print("\nPART 11 COMPLETE")
    print(
        "DECISION RULE: DO NOT ADD ATR FILTER UNLESS "
        "EXPECTANCY + PF IMPROVE WITH ADEQUATE TRADE COUNT."
    )


    # ================================================================
    # PART 13 - FINAL CHRONOLOGICAL OUT-OF-SAMPLE VALIDATION REPORT
    # ================================================================

    def p13_metrics(st):
        trades = st["trades"]

        if trades <= 0:
            return {
                "trades": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "pf": 0.0,
                "total_pnl": 0.0,
            }

        win_rate = st["wins"] / trades * 100.0
        avg_pnl = st["total_pnl"] / trades

        if st["gross_loss"] > 0:
            pf = st["gross_profit"] / st["gross_loss"]
        elif st["gross_profit"] > 0:
            pf = 999.0
        else:
            pf = 0.0

        return {
            "trades": trades,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "pf": pf,
            "total_pnl": st["total_pnl"],
        }

    train_candidates = []

    for key, st in train_stats.items():
        train_m = p13_metrics(st)

        if (
            train_m["trades"] >= 15
            and train_m["avg_pnl"] > 0
            and train_m["pf"] >= 1.20
            and train_m["pf"] < 900
        ):
            train_candidates.append(
                (
                    train_m["avg_pnl"],
                    train_m["pf"],
                    train_m["trades"],
                    key,
                    train_m,
                )
            )

    train_candidates.sort(
        key=lambda x: (x[0], x[1], x[2]),
        reverse=True,
    )

    print("\n" + "=" * 120)
    print("PART 13 - FINAL CHRONOLOGICAL OUT-OF-SAMPLE VALIDATION")
    print("=" * 120)

    print(
        "TRAIN:",
        len(train_days),
        "DAYS",
        min(train_days),
        "TO",
        max(train_days),
    )

    print(
        "OOS:",
        len(oos_days),
        "DAYS",
        min(oos_days),
        "TO",
        max(oos_days),
    )

    print("SELECTION: TRAIN DATA ONLY")
    print("VALIDATION: SAME EXACT CONFIGURATION ON UNTOUCHED OOS")
    print("=" * 120)

    if not train_candidates:
        print("NO ELIGIBLE TRAIN CONFIGURATIONS")

    else:
        for rank, item in enumerate(train_candidates[:20], 1):
            _, _, _, key, train_m = item

            (
                setup_name,
                atr_name,
                expansion_name,
                range_name,
                mode,
                target_pct,
                stop_pct,
            ) = key

            oos_m = p13_metrics(oos_stats[key])

            if train_m["avg_pnl"] != 0:
                retention = (
                    oos_m["avg_pnl"]
                    / train_m["avg_pnl"]
                    * 100.0
                )
            else:
                retention = 0.0

            passed = (
                oos_m["trades"] >= 5
                and oos_m["avg_pnl"] > 0
                and oos_m["pf"] >= 1.0
            )

            verdict = "OOS_PASS" if passed else "OOS_FAIL"

            print(
                "\nRANK", rank,
                "| SETUP", setup_name,
                "|", atr_name,
                "|", expansion_name,
                "|", range_name,
                "|", mode,
                "| TARGET", target_pct, "%",
                "| SL", stop_pct, "%",
            )

            print(
                "   TRAIN",
                "| TRADES", train_m["trades"],
                "| WIN_RATE", round(train_m["win_rate"], 2), "%",
                "| AVG_PNL", round(train_m["avg_pnl"], 4), "%",
                "| PF", round(train_m["pf"], 3),
                "| TOTAL_PNL", round(train_m["total_pnl"], 4), "%",
            )

            print(
                "   OOS  ",
                "| TRADES", oos_m["trades"],
                "| WIN_RATE", round(oos_m["win_rate"], 2), "%",
                "| AVG_PNL", round(oos_m["avg_pnl"], 4), "%",
                "| PF", round(oos_m["pf"], 3),
                "| TOTAL_PNL", round(oos_m["total_pnl"], 4), "%",
                "| EXPECTANCY_RETENTION", round(retention, 1), "%",
                "|", verdict,
            )

    print("\nPART 13 COMPLETE")
    print(
        "DECISION RULE: PROMOTE ONLY CONFIGURATIONS THAT REMAIN "
        "PROFITABLE ON UNTOUCHED OOS DATA WITH ADEQUATE SAMPLE SIZE."
    )

    # ================================================================
    # PART 14 - OOS FAILURE DIAGNOSIS
    # Diagnosis only. Do not optimize parameters on OOS.
    # ================================================================

    def p14_aggregate_stats(stats_map):
        unique_keys = len(stats_map)

        total_trades = 0
        total_pnl = 0.0
        gross_profit = 0.0
        gross_loss = 0.0

        atr_sum = 0.0
        expansion_sum = 0.0
        range_atr_sum = 0.0
        weighted_count = 0

        mode_summary = defaultdict(
            lambda: {
                "keys": 0,
                "trades": 0,
                "total_pnl": 0.0,
            }
        )

        for key, st in stats_map.items():
            trades = st["trades"]

            if trades <= 0:
                continue

            total_trades += trades
            total_pnl += st["total_pnl"]
            gross_profit += st["gross_profit"]
            gross_loss += st["gross_loss"]

            atr_sum += st["atr_pct_sum"]
            expansion_sum += st["atr_expansion_sum"]
            range_atr_sum += st["range_atr_sum"]
            weighted_count += trades

            mode = key[4]

            mode_summary[mode]["keys"] += 1
            mode_summary[mode]["trades"] += trades
            mode_summary[mode]["total_pnl"] += st["total_pnl"]

        if total_trades > 0:
            avg_pnl = total_pnl / total_trades
        else:
            avg_pnl = 0.0

        if gross_loss > 0:
            pf = gross_profit / gross_loss
        elif gross_profit > 0:
            pf = 999.0
        else:
            pf = 0.0

        if weighted_count > 0:
            avg_atr = atr_sum / weighted_count
            avg_expansion = expansion_sum / weighted_count
            avg_range_atr = range_atr_sum / weighted_count
        else:
            avg_atr = 0.0
            avg_expansion = 0.0
            avg_range_atr = 0.0

        return {
            "unique_keys": unique_keys,
            "trades": total_trades,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "pf": pf,
            "avg_atr": avg_atr,
            "avg_expansion": avg_expansion,
            "avg_range_atr": avg_range_atr,
            "modes": mode_summary,
        }

    train_diag = p14_aggregate_stats(train_stats)
    oos_diag = p14_aggregate_stats(oos_stats)

    print("\n" + "=" * 120)
    print("PART 14 - OOS FAILURE DIAGNOSIS")
    print("PURPOSE: COMPARE TRAIN VS OOS REGIME CHARACTERISTICS")
    print("RULE: DIAGNOSIS ONLY - DO NOT OPTIMIZE PARAMETERS ON OOS")
    print("=" * 120)

    print(
        "TRAIN AGGREGATE",
        "| CONFIG_KEYS", train_diag["unique_keys"],
        "| WEIGHTED_TRADES", train_diag["trades"],
        "| AVG_PNL", round(train_diag["avg_pnl"], 4), "%",
        "| PF", round(train_diag["pf"], 3),
        "| AVG_ATR", round(train_diag["avg_atr"], 4), "%",
        "| AVG_EXP", round(train_diag["avg_expansion"], 3),
        "| AVG_RANGE_ATR", round(train_diag["avg_range_atr"], 3),
    )

    print(
        "OOS AGGREGATE  ",
        "| CONFIG_KEYS", oos_diag["unique_keys"],
        "| WEIGHTED_TRADES", oos_diag["trades"],
        "| AVG_PNL", round(oos_diag["avg_pnl"], 4), "%",
        "| PF", round(oos_diag["pf"], 3),
        "| AVG_ATR", round(oos_diag["avg_atr"], 4), "%",
        "| AVG_EXP", round(oos_diag["avg_expansion"], 3),
        "| AVG_RANGE_ATR", round(oos_diag["avg_range_atr"], 3),
    )

    print("\nTIME REGIME COMPARISON")

    all_modes = sorted(
        set(train_diag["modes"])
        | set(oos_diag["modes"])
    )

    for mode in all_modes:
        tr = train_diag["modes"].get(
            mode,
            {"keys": 0, "trades": 0, "total_pnl": 0.0},
        )
        oo = oos_diag["modes"].get(
            mode,
            {"keys": 0, "trades": 0, "total_pnl": 0.0},
        )

        tr_avg = (
            tr["total_pnl"] / tr["trades"]
            if tr["trades"] > 0
            else 0.0
        )

        oo_avg = (
            oo["total_pnl"] / oo["trades"]
            if oo["trades"] > 0
            else 0.0
        )

        print(
            "MODE", mode,
            "| TRAIN_TRADES", tr["trades"],
            "| TRAIN_AVG_PNL", round(tr_avg, 4), "%",
            "| OOS_TRADES", oo["trades"],
            "| OOS_AVG_PNL", round(oo_avg, 4), "%",
        )

    print("\nPART 14 DIAGNOSIS COMPLETE")

    print("\n" + "=" * 120)
    print("PART 14B - UNIQUE CONFIRMED EVENT-LEVEL REGIME DIAGNOSIS")
    print("COUNTING RULE: EACH CONFIRMED VALID-ATR EVENT COUNTED ONCE")
    print("=" * 120)

    for split_name in ("TRAIN", "OOS"):
        events = p14_unique_events[split_name]
        if not events:
            print(split_name, "| UNIQUE_EVENTS 0")
            continue

        avg_atr = sum(x["atr_pct"] for x in events) / len(events)
        avg_exp = sum(x["atr_expansion"] for x in events) / len(events)
        avg_range = sum(x["range_atr"] for x in events) / len(events)

        print(
            split_name,
            "| UNIQUE_EVENTS", len(events),
            "| AVG_ATR", round(avg_atr, 4), "%",
            "| AVG_EXP", round(avg_exp, 3),
            "| AVG_RANGE_ATR", round(avg_range, 3),
        )

    print("\nUNIQUE EVENT TIME REGIME COMPARISON")

    for mode in ("OPEN", "MID", "AFTERNOON"):
        train_count = sum(
            1 for x in p14_unique_events["TRAIN"]
            if x["time_mode"] == mode
        )
        oos_count = sum(
            1 for x in p14_unique_events["OOS"]
            if x["time_mode"] == mode
        )

        print(
            "MODE", mode,
            "| TRAIN_EVENTS", train_count,
            "| OOS_EVENTS", oos_count,
        )

    print("\nPART 14B COMPLETE")

    # ================================================================
    # PART 15 - UNIQUE TRADE OUTCOME VALIDATION
    # Each confirmed valid-ATR event is counted exactly once.
    # No configuration-key duplication.
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 15 - UNIQUE TRADE OUTCOME VALIDATION")
    print("COUNTING RULE: EACH CONFIRMED VALID-ATR TRADE EVENT COUNTED ONCE")
    print("TRAIN/OOS SPLIT: SAME CHRONOLOGICAL SPLIT AS PART 13")
    print("=" * 120)

    for target_pct in P10_TARGETS:
        for stop_pct in P10_STOPS:
            print(
                "\nTARGET", target_pct, "%",
                "| SL", stop_pct, "%",
            )

            for split_name in ("TRAIN", "OOS"):
                events = p15_trade_events[split_name]

                trades = 0
                wins = 0
                losses = 0
                time_exits = 0
                total_pnl = 0.0
                gross_profit = 0.0
                gross_loss = 0.0

                for event in events:
                    result, pnl_pct = p6_simulate_short(
                        event["entry"],
                        event["future"],
                        target_pct,
                        stop_pct,
                    )

                    trades += 1
                    total_pnl += pnl_pct

                    if pnl_pct > 0:
                        gross_profit += pnl_pct
                    elif pnl_pct < 0:
                        gross_loss += abs(pnl_pct)

                    if result == "WIN":
                        wins += 1
                    elif result == "LOSS":
                        losses += 1
                    else:
                        time_exits += 1

                win_rate = (
                    wins / trades * 100.0
                    if trades > 0
                    else 0.0
                )

                avg_pnl = (
                    total_pnl / trades
                    if trades > 0
                    else 0.0
                )

                if gross_loss > 0:
                    pf = gross_profit / gross_loss
                elif gross_profit > 0:
                    pf = 999.0
                else:
                    pf = 0.0

                print(
                    split_name,
                    "| TRADES", trades,
                    "| WINS", wins,
                    "| LOSSES", losses,
                    "| TIME_EXIT", time_exits,
                    "| WIN_RATE", round(win_rate, 2), "%",
                    "| AVG_PNL", round(avg_pnl, 4), "%",
                    "| TOTAL_PNL", round(total_pnl, 4), "%",
                    "| PF", round(pf, 3),
                )

    print("\nPART 15 COMPLETE")

    # ================================================================
    # PART 16 - UNIQUE EVENT REGIME STABILITY DIAGNOSIS
    # Fixed outcome model: Target 0.12%, SL 0.10%.
    # Diagnose broad pre-existing regimes; do not optimize on OOS.
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 16 - UNIQUE EVENT REGIME STABILITY DIAGNOSIS")
    print("FIXED OUTCOME MODEL: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("RULE: BROAD REGIME DIAGNOSIS ONLY - DO NOT SELECT PARAMETERS FROM OOS")
    print("=" * 120)

    p16_target = 0.12
    p16_stop = 0.10

    def p16_metrics(events):
        trades = 0
        wins = 0
        losses = 0
        time_exits = 0
        total_pnl = 0.0
        gross_profit = 0.0
        gross_loss = 0.0

        for event in events:
            result, pnl_pct = p6_simulate_short(
                event["entry"],
                event["future"],
                p16_target,
                p16_stop,
            )

            trades += 1
            total_pnl += pnl_pct

            if pnl_pct > 0:
                gross_profit += pnl_pct
            elif pnl_pct < 0:
                gross_loss += abs(pnl_pct)

            if result == "WIN":
                wins += 1
            elif result == "LOSS":
                losses += 1
            else:
                time_exits += 1

        win_rate = wins / trades * 100.0 if trades else 0.0
        avg_pnl = total_pnl / trades if trades else 0.0

        if gross_loss > 0:
            pf = gross_profit / gross_loss
        elif gross_profit > 0:
            pf = 999.0
        else:
            pf = 0.0

        return {
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "time_exits": time_exits,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "pf": pf,
        }

    def p16_print_row(label, train_events, oos_events):
        tr = p16_metrics(train_events)
        oo = p16_metrics(oos_events)

        print(
            label,
            "| TRAIN", tr["trades"],
            "WR", round(tr["win_rate"], 2),
            "AVG", round(tr["avg_pnl"], 4),
            "PF", round(tr["pf"], 3),
            "| OOS", oo["trades"],
            "WR", round(oo["win_rate"], 2),
            "AVG", round(oo["avg_pnl"], 4),
            "PF", round(oo["pf"], 3),
        )

    train_events = p15_trade_events["TRAIN"]
    oos_events = p15_trade_events["OOS"]

    print("\nBASELINE")
    p16_print_row("ALL EVENTS", train_events, oos_events)

    print("\nTIME REGIMES")
    for mode in ("OPEN", "MID", "AFTERNOON"):
        tr_filtered = [
            e for e in train_events
            if e["time_mode"] == mode
        ]
        oo_filtered = [
            e for e in oos_events
            if e["time_mode"] == mode
        ]
        p16_print_row(mode, tr_filtered, oo_filtered)

    print("\nMIN ATR REGIMES")
    for threshold in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20):
        tr_filtered = [
            e for e in train_events
            if e["atr_pct"] >= threshold
        ]
        oo_filtered = [
            e for e in oos_events
            if e["atr_pct"] >= threshold
        ]
        p16_print_row("ATR >= " + str(threshold), tr_filtered, oo_filtered)

    print("\nMIN ATR EXPANSION REGIMES")
    for threshold in (1.00, 1.05, 1.10, 1.20):
        tr_filtered = [
            e for e in train_events
            if e["atr_expansion"] >= threshold
        ]
        oo_filtered = [
            e for e in oos_events
            if e["atr_expansion"] >= threshold
        ]
        p16_print_row("EXP >= " + str(threshold), tr_filtered, oo_filtered)

    print("\nMIN RANGE/ATR REGIMES")
    for threshold in (0.50, 0.75, 1.00, 1.25, 1.50):
        tr_filtered = [
            e for e in train_events
            if e["range_atr"] >= threshold
        ]
        oo_filtered = [
            e for e in oos_events
            if e["range_atr"] >= threshold
        ]
        p16_print_row("RANGE_ATR >= " + str(threshold), tr_filtered, oo_filtered)

    print("\nPART 16 COMPLETE")

    # ================================================================
    # PART 17 - MID REGIME ROBUSTNESS VALIDATION
    # Primary regime selected from broad Part 16 diagnosis: MID.
    # Fixed Target/SL. Compare simple incremental filters only.
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 17 - MID REGIME ROBUSTNESS VALIDATION")
    print("PRIMARY REGIME: MID")
    print("FIXED OUTCOME MODEL: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("RULE: TEST SIMPLE INCREMENTAL FILTERS - AVOID OOS PARAMETER OPTIMIZATION")
    print("=" * 120)

    p17_train_mid = [
        e for e in p15_trade_events["TRAIN"]
        if e["time_mode"] == "MID"
    ]

    p17_oos_mid = [
        e for e in p15_trade_events["OOS"]
        if e["time_mode"] == "MID"
    ]

    p17_tests = [
        (
            "MID_BASELINE",
            lambda e: True,
        ),
        (
            "MID_RANGE_ATR_GE_0.75",
            lambda e: e["range_atr"] >= 0.75,
        ),
        (
            "MID_RANGE_ATR_GE_1.0",
            lambda e: e["range_atr"] >= 1.0,
        ),
        (
            "MID_EXP_GE_1.0",
            lambda e: e["atr_expansion"] >= 1.0,
        ),
        (
            "MID_EXP_GE_1.05",
            lambda e: e["atr_expansion"] >= 1.05,
        ),
        (
            "MID_RANGE_GE_1.0_EXP_GE_1.0",
            lambda e: (
                e["range_atr"] >= 1.0
                and e["atr_expansion"] >= 1.0
            ),
        ),
        (
            "MID_P4_BASE",
            lambda e: "P4_BASE" in e["setups"],
        ),
        (
            "MID_P4_BREAK_LOW_EMA_BEAR",
            lambda e: "P4_BREAK_LOW_EMA_BEAR" in e["setups"],
        ),
    ]

    print("\nROBUSTNESS RESULTS")

    for label, rule in p17_tests:
        tr_events = [
            e for e in p17_train_mid
            if rule(e)
        ]

        oo_events = [
            e for e in p17_oos_mid
            if rule(e)
        ]

        tr = p16_metrics(tr_events)
        oo = p16_metrics(oo_events)

        train_days_count = len(train_days)
        oos_days_count = len(oos_days)

        tr_per_day = (
            tr["trades"] / train_days_count
            if train_days_count
            else 0.0
        )

        oo_per_day = (
            oo["trades"] / oos_days_count
            if oos_days_count
            else 0.0
        )

        print("\n" + label)
        print(
            "TRAIN",
            "| TRADES", tr["trades"],
            "| TRADES/DAY", round(tr_per_day, 3),
            "| WINS", tr["wins"],
            "| LOSSES", tr["losses"],
            "| TIME_EXIT", tr["time_exits"],
            "| WIN_RATE", round(tr["win_rate"], 2), "%",
            "| AVG_PNL", round(tr["avg_pnl"], 4), "%",
            "| PF", round(tr["pf"], 3),
        )
        print(
            "OOS  ",
            "| TRADES", oo["trades"],
            "| TRADES/DAY", round(oo_per_day, 3),
            "| WINS", oo["wins"],
            "| LOSSES", oo["losses"],
            "| TIME_EXIT", oo["time_exits"],
            "| WIN_RATE", round(oo["win_rate"], 2), "%",
            "| AVG_PNL", round(oo["avg_pnl"], 4), "%",
            "| PF", round(oo["pf"], 3),
        )

    print("\nPART 17 COMPLETE")

    # ================================================================
    # PART 18 - FIXED RULE WALK-FORWARD STABILITY
    # Candidate frozen before this test:
    # MID + RANGE_ATR >= 0.75 | Target 0.12% | SL 0.10% | Horizon 5
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 18 - FIXED RULE WALK-FORWARD STABILITY")
    print("FROZEN RULE: MID + RANGE_ATR >= 0.75")
    print("OUTCOME: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("RULE: NO PARAMETER CHANGES BETWEEN CHRONOLOGICAL BLOCKS")
    print("=" * 120)

    p18_all_events = (
        p15_trade_events["TRAIN"]
        + p15_trade_events["OOS"]
    )

    p18_candidate_events = [
        e for e in p18_all_events
        if (
            e["time_mode"] == "MID"
            and e["range_atr"] >= 0.75
        )
    ]

    p18_all_days = sorted(set(
        e["dt"].date()
        for e in p18_all_events
    ))

    p18_num_blocks = 5
    p18_day_count = len(p18_all_days)

    print(
        "TOTAL DAYS", p18_day_count,
        "| CANDIDATE TRADES", len(p18_candidate_events),
        "| BLOCKS", p18_num_blocks,
    )

    p18_positive_blocks = 0
    p18_profitable_pf_blocks = 0

    for block_idx in range(p18_num_blocks):
        start_idx = (
            block_idx * p18_day_count
            // p18_num_blocks
        )
        end_idx = (
            (block_idx + 1) * p18_day_count
            // p18_num_blocks
        )

        block_days = set(
            p18_all_days[start_idx:end_idx]
        )

        if not block_days:
            continue

        block_events = [
            e for e in p18_candidate_events
            if e["dt"].date() in block_days
        ]

        m = p16_metrics(block_events)

        if m["avg_pnl"] > 0:
            p18_positive_blocks += 1

        if m["pf"] > 1.0:
            p18_profitable_pf_blocks += 1

        print("\nBLOCK", block_idx + 1)
        print(
            "PERIOD", min(block_days), "TO", max(block_days),
            "| DAYS", len(block_days),
        )
        print(
            "TRADES", m["trades"],
            "| WINS", m["wins"],
            "| LOSSES", m["losses"],
            "| TIME_EXIT", m["time_exits"],
            "| WIN_RATE", round(m["win_rate"], 2), "%",
            "| AVG_PNL", round(m["avg_pnl"], 4), "%",
            "| TOTAL_PNL", round(m["total_pnl"], 4), "%",
            "| PF", round(m["pf"], 3),
        )

    print("\nWALK-FORWARD SUMMARY")
    print(
        "POSITIVE AVG_PNL BLOCKS",
        p18_positive_blocks,
        "/",
        p18_num_blocks,
    )
    print(
        "PF > 1 BLOCKS",
        p18_profitable_pf_blocks,
        "/",
        p18_num_blocks,
    )

    print("\nPART 18 COMPLETE")








    print("\n" + "=" * 120)
    print("PART 19 - BLOCK 3 FAILURE REGIME DIAGNOSIS")
    print("FROZEN RULE: MID + RANGE_ATR >= 0.75")
    print("PURPOSE: COMPARE FAILED BLOCK 3 WITH OTHER WALK-FORWARD BLOCKS")
    print("RULE: DIAGNOSIS ONLY - NO PARAMETER OPTIMIZATION")
    print("=" * 120)

    p19_events = [
        e for e in p18_candidate_events
    ]

    for block_no in range(p18_num_blocks):
        start_idx = (
            block_no * p18_day_count
            // p18_num_blocks
        )
        end_idx = (
            (block_no + 1) * p18_day_count
            // p18_num_blocks
        )

        block_days = set(
            p18_all_days[start_idx:end_idx]
        )

        if not block_days:
            continue

        events = [
            e for e in p19_events
            if e["dt"].date() in block_days
        ]

        print("\nBLOCK", block_no + 1)

        if not events:
            print(
                "PERIOD", min(block_days), "TO", max(block_days),
                "| DAYS", len(block_days),
                "| TRADES 0"
            )
            continue

        avg_atr = (
            sum(e["atr_pct"] for e in events)
            / len(events)
        )
        avg_exp = (
            sum(e["atr_expansion"] for e in events)
            / len(events)
        )
        avg_range = (
            sum(e["range_atr"] for e in events)
            / len(events)
        )

        atr_ge_01 = sum(
            1 for e in events
            if e["atr_pct"] >= 0.10
        )
        exp_ge_1 = sum(
            1 for e in events
            if e["atr_expansion"] >= 1.0
        )
        range_ge_1 = sum(
            1 for e in events
            if e["range_atr"] >= 1.0
        )

        print(
            "PERIOD", min(block_days), "TO", max(block_days),
            "| DAYS", len(block_days),
            "| TRADES", len(events)
        )
        print(
            "AVG_ATR", round(avg_atr, 4), "%",
            "| AVG_EXP", round(avg_exp, 3),
            "| AVG_RANGE_ATR", round(avg_range, 3)
        )
        print(
            "ATR_GE_0.10", atr_ge_01,
            round(100.0 * atr_ge_01 / len(events), 2), "%",
            "| EXP_GE_1.0", exp_ge_1,
            round(100.0 * exp_ge_1 / len(events), 2), "%",
            "| RANGE_GE_1.0", range_ge_1,
            round(100.0 * range_ge_1 / len(events), 2), "%"
        )

    print("\nPART 19 COMPLETE")



    print("\n" + "=" * 120)
    print("PART 20 - MARKET STRUCTURE WALK-FORWARD DIAGNOSIS")
    print("BASELINE: MID + RANGE_ATR >= 0.75")
    print("STRUCTURE TEST: P4_BREAK_LOW_EMA_BEAR")
    print("OUTCOME: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("RULE: SAME EXACT 5 CHRONOLOGICAL BLOCKS AS PART 18")
    print("=" * 120)

    p20_structure_events = [
        e for e in p18_candidate_events
        if "P4_BREAK_LOW_EMA_BEAR" in e["setups"]
    ]

    print(
        "BASELINE EVENTS", len(p18_candidate_events),
        "| STRUCTURE EVENTS", len(p20_structure_events)
    )

    for block_idx in range(p18_num_blocks):
        start_idx = (
            block_idx * p18_day_count
            // p18_num_blocks
        )
        end_idx = (
            (block_idx + 1) * p18_day_count
            // p18_num_blocks
        )

        block_days = set(
            p18_all_days[start_idx:end_idx]
        )

        if not block_days:
            continue

        baseline_events = [
            e for e in p18_candidate_events
            if e["dt"].date() in block_days
        ]

        structure_events = [
            e for e in p20_structure_events
            if e["dt"].date() in block_days
        ]

        baseline_m = p16_metrics(baseline_events)
        structure_m = p16_metrics(structure_events)

        print("\nBLOCK", block_idx + 1)
        print(
            "PERIOD", min(block_days), "TO", max(block_days),
            "| DAYS", len(block_days)
        )

        print(
            "BASELINE",
            "| TRADES", baseline_m["trades"],
            "| WINS", baseline_m["wins"],
            "| LOSSES", baseline_m["losses"],
            "| TIME_EXIT", baseline_m["time_exits"],
            "| WIN_RATE", round(baseline_m["win_rate"], 2), "%",
            "| AVG_PNL", round(baseline_m["avg_pnl"], 4), "%",
            "| PF", round(baseline_m["pf"], 3)
        )

        print(
            "STRUCTURE",
            "| TRADES", structure_m["trades"],
            "| WINS", structure_m["wins"],
            "| LOSSES", structure_m["losses"],
            "| TIME_EXIT", structure_m["time_exits"],
            "| WIN_RATE", round(structure_m["win_rate"], 2), "%",
            "| AVG_PNL", round(structure_m["avg_pnl"], 4), "%",
            "| PF", round(structure_m["pf"], 3)
        )

    p20_all_baseline = p16_metrics(
        p18_candidate_events
    )

    p20_all_structure = p16_metrics(
        p20_structure_events
    )

    print("\nOVERALL COMPARISON")

    print(
        "BASELINE",
        "| TRADES", p20_all_baseline["trades"],
        "| WIN_RATE", round(p20_all_baseline["win_rate"], 2), "%",
        "| AVG_PNL", round(p20_all_baseline["avg_pnl"], 4), "%",
        "| TOTAL_PNL", round(p20_all_baseline["total_pnl"], 4), "%",
        "| PF", round(p20_all_baseline["pf"], 3)
    )

    print(
        "STRUCTURE",
        "| TRADES", p20_all_structure["trades"],
        "| WIN_RATE", round(p20_all_structure["win_rate"], 2), "%",
        "| AVG_PNL", round(p20_all_structure["avg_pnl"], 4), "%",
        "| TOTAL_PNL", round(p20_all_structure["total_pnl"], 4), "%",
        "| PF", round(p20_all_structure["pf"], 3)
    )

    print("\nPART 20 COMPLETE")

if __name__ == "__main__":
    part10_main()

