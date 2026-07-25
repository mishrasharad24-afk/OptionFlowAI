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
                "signal_close": signal_candle["c"],
                "confirm_close": confirm["c"],
                "features": dict(f),
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


    # ================================================================
    # PART 21 - WIN/LOSS + MAE/MFE DIAGNOSIS
    # Frozen candidate: MID + RANGE_ATR >= 0.75
    # Outcome model: Target 0.12% | SL 0.10% | Horizon 5
    # Diagnostic only - no parameter optimization
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 21 - WIN/LOSS + MAE/MFE DIAGNOSIS")
    print("FROZEN RULE: MID + RANGE_ATR >= 0.75")
    print("OUTCOME: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("PURPOSE: COMPARE WIN / LOSS / TIME_EXIT AND ENTRY EXCURSION")
    print("RULE: DIAGNOSIS ONLY - NO NEW FILTER SELECTION")
    print("=" * 120)

    p21_events = p18_candidate_events

    def p21_trade_detail(e):
        entry = e["entry"]
        future = e["future"]

        result, pnl = p6_simulate_short(
            entry,
            future,
            0.12,
            0.10,
        )

        # Short-trade excursion:
        # MFE = maximum favorable downward move
        # MAE = maximum adverse upward move
        mfe_pct = max(
            (entry - c["l"]) / entry * 100.0
            for c in future
        )

        mae_pct = max(
            (c["h"] - entry) / entry * 100.0
            for c in future
        )

        return {
            "event": e,
            "result": result,
            "pnl": pnl,
            "mfe_pct": mfe_pct,
            "mae_pct": mae_pct,
        }

    p21_details = [
        p21_trade_detail(e)
        for e in p21_events
    ]

    print("\nTOTAL EVENTS", len(p21_details))

    for result_name in ("WIN", "LOSS", "TIME_EXIT"):

        rows = [
            x for x in p21_details
            if x["result"] == result_name
        ]

        print("\n" + result_name)

        if not rows:
            print("NO EVENTS")
            continue

        avg_atr = sum(
            x["event"]["atr_pct"]
            for x in rows
        ) / len(rows)

        avg_exp = sum(
            x["event"]["atr_expansion"]
            for x in rows
        ) / len(rows)

        avg_range = sum(
            x["event"]["range_atr"]
            for x in rows
        ) / len(rows)

        avg_mfe = sum(
            x["mfe_pct"]
            for x in rows
        ) / len(rows)

        avg_mae = sum(
            x["mae_pct"]
            for x in rows
        ) / len(rows)

        avg_pnl = sum(
            x["pnl"]
            for x in rows
        ) / len(rows)

        print(
            "TRADES", len(rows),
            "| AVG_PNL", round(avg_pnl, 4), "%",
        )

        print(
            "AVG_ATR", round(avg_atr, 4), "%",
            "| AVG_EXP", round(avg_exp, 3),
            "| AVG_RANGE_ATR", round(avg_range, 3),
        )

        print(
            "AVG_MFE", round(avg_mfe, 4), "%",
            "| AVG_MAE", round(avg_mae, 4), "%",
        )

    # ------------------------------------------------
    # Entry-time diagnosis
    # ------------------------------------------------

    print("\nENTRY TIME DIAGNOSIS")

    p21_time_groups = {
        "MID_EARLY": [],
        "MID_LATE": [],
    }

    for x in p21_details:
        dt = x["event"]["dt"]

        # MID regime split diagnostically into two halves.
        # No filtering decision is made here.
        if dt.hour < 12:
            p21_time_groups["MID_EARLY"].append(x)
        else:
            p21_time_groups["MID_LATE"].append(x)

    for name, rows in p21_time_groups.items():

        if not rows:
            continue

        wins = sum(
            1 for x in rows
            if x["result"] == "WIN"
        )

        losses = sum(
            1 for x in rows
            if x["result"] == "LOSS"
        )

        time_exits = sum(
            1 for x in rows
            if x["result"] == "TIME_EXIT"
        )

        total_pnl = sum(
            x["pnl"]
            for x in rows
        )

        avg_pnl = total_pnl / len(rows)

        print(
            name,
            "| TRADES", len(rows),
            "| WINS", wins,
            "| LOSSES", losses,
            "| TIME_EXIT", time_exits,
            "| WIN_RATE", round(100.0 * wins / len(rows), 2), "%",
            "| AVG_PNL", round(avg_pnl, 4), "%",
        )

    # ------------------------------------------------
    # Block-level MAE/MFE diagnosis
    # Same chronological blocks as Part 18
    # ------------------------------------------------

    print("\nBLOCK LEVEL MAE/MFE")

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

        rows = [
            x for x in p21_details
            if x["event"]["dt"].date() in block_days
        ]

        if not rows:
            continue

        avg_mfe = sum(
            x["mfe_pct"]
            for x in rows
        ) / len(rows)

        avg_mae = sum(
            x["mae_pct"]
            for x in rows
        ) / len(rows)

        wins = sum(
            1 for x in rows
            if x["result"] == "WIN"
        )

        losses = sum(
            1 for x in rows
            if x["result"] == "LOSS"
        )

        print(
            "BLOCK", block_idx + 1,
            "| TRADES", len(rows),
            "| WINS", wins,
            "| LOSSES", losses,
            "| AVG_MFE", round(avg_mfe, 4), "%",
            "| AVG_MAE", round(avg_mae, 4), "%",
        )

    print("\nPART 21 COMPLETE")


    # ================================================================
    # PART 22 - RANGE/ATR + EARLY FOLLOW-THROUGH DIAGNOSIS
    # Frozen candidate: MID + RANGE_ATR >= 0.75
    # Outcome: Target 0.12% | SL 0.10% | Horizon 5
    # Diagnostic only - no filter optimization
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 22 - RANGE/ATR + EARLY FOLLOW-THROUGH DIAGNOSIS")
    print("FROZEN RULE: MID + RANGE_ATR >= 0.75")
    print("OUTCOME: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("PURPOSE: TEST EXHAUSTION AND FIRST 1-2 CANDLE FOLLOW-THROUGH")
    print("RULE: DIAGNOSIS ONLY - NO NEW FILTER SELECTION")
    print("=" * 120)

    # Reuse Part 21 details so the exact same 119 candidate events
    # and the exact same outcome model are analyzed.
    p22_details = p21_details

    # ------------------------------------------------
    # RANGE / ATR BUCKET DIAGNOSIS
    # ------------------------------------------------

    print("\nRANGE/ATR BUCKET DIAGNOSIS")

    p22_range_buckets = (
        ("0.75_TO_1.00", 0.75, 1.00),
        ("1.00_TO_1.25", 1.00, 1.25),
        ("1.25_TO_1.50", 1.25, 1.50),
        ("1.50_PLUS", 1.50, None),
    )

    for name, low, high in p22_range_buckets:

        rows = [
            x for x in p22_details
            if (
                x["event"]["range_atr"] >= low
                and (
                    high is None
                    or x["event"]["range_atr"] < high
                )
            )
        ]

        if not rows:
            continue

        wins = sum(
            1 for x in rows
            if x["result"] == "WIN"
        )

        losses = sum(
            1 for x in rows
            if x["result"] == "LOSS"
        )

        time_exits = sum(
            1 for x in rows
            if x["result"] == "TIME_EXIT"
        )

        avg_pnl = sum(
            x["pnl"]
            for x in rows
        ) / len(rows)

        avg_mfe = sum(
            x["mfe_pct"]
            for x in rows
        ) / len(rows)

        avg_mae = sum(
            x["mae_pct"]
            for x in rows
        ) / len(rows)

        print(
            name,
            "| TRADES", len(rows),
            "| WINS", wins,
            "| LOSSES", losses,
            "| TIME_EXIT", time_exits,
            "| WIN_RATE", round(100.0 * wins / len(rows), 2), "%",
            "| AVG_PNL", round(avg_pnl, 4), "%",
            "| AVG_MFE", round(avg_mfe, 4), "%",
            "| AVG_MAE", round(avg_mae, 4), "%",
        )

    # ------------------------------------------------
    # EARLY FOLLOW-THROUGH
    # Short trade:
    # Favorable = price moves down from entry
    # Adverse   = price moves up from entry
    # ------------------------------------------------

    print("\nFIRST 1-2 CANDLE FOLLOW-THROUGH")

    for candle_count in (1, 2):

        print("\nFIRST", candle_count, "CANDLE(S)")

        for result_name in ("WIN", "LOSS", "TIME_EXIT"):

            rows = [
                x for x in p22_details
                if x["result"] == result_name
            ]

            if not rows:
                continue

            favorable_values = []
            adverse_values = []
            close_move_values = []

            for x in rows:

                entry = x["event"]["entry"]
                future = x["event"]["future"][:candle_count]

                if not future:
                    continue

                favorable = max(
                    (entry - c["l"]) / entry * 100.0
                    for c in future
                )

                adverse = max(
                    (c["h"] - entry) / entry * 100.0
                    for c in future
                )

                # Positive close_move means favorable move for short.
                close_move = (
                    (entry - future[-1]["c"])
                    / entry
                    * 100.0
                )

                favorable_values.append(favorable)
                adverse_values.append(adverse)
                close_move_values.append(close_move)

            if not favorable_values:
                continue

            print(
                result_name,
                "| TRADES", len(favorable_values),
                "| AVG_FAVORABLE",
                round(
                    sum(favorable_values)
                    / len(favorable_values),
                    4,
                ),
                "%",
                "| AVG_ADVERSE",
                round(
                    sum(adverse_values)
                    / len(adverse_values),
                    4,
                ),
                "%",
                "| AVG_CLOSE_MOVE",
                round(
                    sum(close_move_values)
                    / len(close_move_values),
                    4,
                ),
                "%",
            )

    # ------------------------------------------------
    # EARLY DIRECTIONAL STATE DIAGNOSIS
    # Based on close after candle 1 and candle 2.
    # This is descriptive only.
    # ------------------------------------------------

    print("\nEARLY CLOSE DIRECTION STATE")

    for candle_index in (0, 1):

        groups = {
            "FAVORABLE_CLOSE": [],
            "ADVERSE_OR_FLAT_CLOSE": [],
        }

        for x in p22_details:

            future = x["event"]["future"]

            if len(future) <= candle_index:
                continue

            entry = x["event"]["entry"]
            close_price = future[candle_index]["c"]

            if close_price < entry:
                groups["FAVORABLE_CLOSE"].append(x)
            else:
                groups["ADVERSE_OR_FLAT_CLOSE"].append(x)

        print("\nAFTER CANDLE", candle_index + 1)

        for name, rows in groups.items():

            if not rows:
                continue

            wins = sum(
                1 for x in rows
                if x["result"] == "WIN"
            )

            losses = sum(
                1 for x in rows
                if x["result"] == "LOSS"
            )

            time_exits = sum(
                1 for x in rows
                if x["result"] == "TIME_EXIT"
            )

            avg_pnl = sum(
                x["pnl"]
                for x in rows
            ) / len(rows)

            print(
                name,
                "| TRADES", len(rows),
                "| WINS", wins,
                "| LOSSES", losses,
                "| TIME_EXIT", time_exits,
                "| WIN_RATE",
                round(100.0 * wins / len(rows), 2),
                "%",
                "| AVG_PNL",
                round(avg_pnl, 4),
                "%",
            )

    print("\nPART 22 COMPLETE")


    # ================================================================
    # PART 23 - EARLY FAILURE EXIT SIMULATION
    # Frozen entry: MID + RANGE_ATR >= 0.75
    # Baseline: Target 0.12% | SL 0.10% | Horizon 5
    # Test: Exit after candle 1 or 2 if close is adverse/flat
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 23 - EARLY FAILURE EXIT SIMULATION")
    print("FROZEN ENTRY RULE: MID + RANGE_ATR >= 0.75")
    print("BASELINE: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("TEST: EARLY EXIT IF CHECK-CANDLE CLOSE >= ENTRY")
    print("PURPOSE: TEST TRADE MANAGEMENT WITHOUT CHANGING ENTRY SIGNALS")
    print("=" * 120)

    p23_events = p18_candidate_events

    def p23_baseline(e):
        result, pnl = p6_simulate_short(
            e["entry"],
            e["future"],
            0.12,
            0.10,
        )
        return result, pnl

    def p23_early_exit(e, check_candle):

        entry = e["entry"]
        future = e["future"]

        target_price = entry * (1.0 - 0.12 / 100.0)
        stop_price = entry * (1.0 + 0.10 / 100.0)

        # Process candles sequentially.
        for idx, candle in enumerate(future):

            stop_hit = candle["h"] >= stop_price
            target_hit = candle["l"] <= target_price

            # Same conservative OHLC rule as baseline.
            if stop_hit and target_hit:
                return "LOSS", -0.10, "NORMAL_SL"

            if stop_hit:
                return "LOSS", -0.10, "NORMAL_SL"

            if target_hit:
                return "WIN", 0.12, "NORMAL_TARGET"

            # After requested candle, exit if close is adverse or flat.
            if idx + 1 == check_candle:
                if candle["c"] >= entry:
                    pnl = (
                        (entry - candle["c"])
                        / entry
                        * 100.0
                    )
                    return "EARLY_EXIT", pnl, "EARLY_FAILURE"

        # Horizon time exit.
        exit_price = future[-1]["c"]
        pnl = (
            (entry - exit_price)
            / entry
            * 100.0
        )

        return "TIME_EXIT", pnl, "HORIZON_EXIT"

    def p23_metrics(rows):

        if not rows:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "time_exits": 0,
                "early_exits": 0,
                "avg_pnl": 0.0,
                "total_pnl": 0.0,
                "pf": 0.0,
            }

        wins = sum(
            1 for x in rows
            if x["result"] == "WIN"
        )

        losses = sum(
            1 for x in rows
            if x["result"] == "LOSS"
        )

        time_exits = sum(
            1 for x in rows
            if x["result"] == "TIME_EXIT"
        )

        early_exits = sum(
            1 for x in rows
            if x["result"] == "EARLY_EXIT"
        )

        total_pnl = sum(
            x["pnl"]
            for x in rows
        )

        avg_pnl = total_pnl / len(rows)

        gross_profit = sum(
            x["pnl"]
            for x in rows
            if x["pnl"] > 0
        )

        gross_loss = -sum(
            x["pnl"]
            for x in rows
            if x["pnl"] < 0
        )

        if gross_loss > 0:
            pf = gross_profit / gross_loss
        elif gross_profit > 0:
            pf = float("inf")
        else:
            pf = 0.0

        return {
            "trades": len(rows),
            "wins": wins,
            "losses": losses,
            "time_exits": time_exits,
            "early_exits": early_exits,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "pf": pf,
        }

    # ------------------------------------------------
    # Build baseline results
    # ------------------------------------------------

    p23_baseline_rows = []

    for e in p23_events:

        result, pnl = p23_baseline(e)

        p23_baseline_rows.append({
            "event": e,
            "result": result,
            "pnl": pnl,
        })

    # ------------------------------------------------
    # Test candle 1 and candle 2 early failure exits
    # ------------------------------------------------

    p23_variants = {}

    for check_candle in (1, 2):

        rows = []

        for e in p23_events:

            result, pnl, reason = p23_early_exit(
                e,
                check_candle,
            )

            rows.append({
                "event": e,
                "result": result,
                "pnl": pnl,
                "reason": reason,
            })

        p23_variants[check_candle] = rows

    print("\nOVERALL COMPARISON")

    baseline_m = p23_metrics(
        p23_baseline_rows
    )

    print(
        "BASELINE",
        "| TRADES", baseline_m["trades"],
        "| WINS", baseline_m["wins"],
        "| LOSSES", baseline_m["losses"],
        "| TIME_EXIT", baseline_m["time_exits"],
        "| AVG_PNL", round(baseline_m["avg_pnl"], 4), "%",
        "| TOTAL_PNL", round(baseline_m["total_pnl"], 4), "%",
        "| PF", round(baseline_m["pf"], 3),
    )

    for check_candle in (1, 2):

        rows = p23_variants[check_candle]
        m = p23_metrics(rows)

        print(
            "EARLY_EXIT_CANDLE_" + str(check_candle),
            "| TRADES", m["trades"],
            "| WINS", m["wins"],
            "| LOSSES", m["losses"],
            "| EARLY_EXIT", m["early_exits"],
            "| TIME_EXIT", m["time_exits"],
            "| AVG_PNL", round(m["avg_pnl"], 4), "%",
            "| TOTAL_PNL", round(m["total_pnl"], 4), "%",
            "| PF", round(m["pf"], 3),
        )

    # ------------------------------------------------
    # Saved losses vs sacrificed winners
    # Compare original baseline outcome with early exit.
    # ------------------------------------------------

    print("\nSAVED LOSSES VS SACRIFICED WINNERS")

    for check_candle in (1, 2):

        variant_rows = p23_variants[check_candle]

        saved_losses = 0
        sacrificed_winners = 0
        early_exit_from_time_exit = 0

        pnl_improvement = 0.0

        for base, variant in zip(
            p23_baseline_rows,
            variant_rows,
        ):

            if variant["result"] != "EARLY_EXIT":
                continue

            if base["result"] == "LOSS":
                saved_losses += 1

            elif base["result"] == "WIN":
                sacrificed_winners += 1

            elif base["result"] == "TIME_EXIT":
                early_exit_from_time_exit += 1

            pnl_improvement += (
                variant["pnl"]
                - base["pnl"]
            )

        print(
            "CANDLE", check_candle,
            "| SAVED_BASELINE_LOSSES", saved_losses,
            "| SACRIFICED_BASELINE_WINNERS", sacrificed_winners,
            "| EARLY_EXIT_FROM_TIME_EXIT", early_exit_from_time_exit,
            "| NET_PNL_CHANGE", round(pnl_improvement, 4), "%",
        )

    # ------------------------------------------------
    # RANGE_ATR < 1.50 diagnostic variant
    # Not selected as a production filter.
    # ------------------------------------------------

    print("\nRANGE_ATR < 1.50 DIAGNOSTIC")

    for label, rows in (
        (
            "BASELINE_RANGE_LT_1.50",
            [
                x for x in p23_baseline_rows
                if x["event"]["range_atr"] < 1.50
            ],
        ),
        (
            "C1_EXIT_RANGE_LT_1.50",
            [
                x for x in p23_variants[1]
                if x["event"]["range_atr"] < 1.50
            ],
        ),
        (
            "C2_EXIT_RANGE_LT_1.50",
            [
                x for x in p23_variants[2]
                if x["event"]["range_atr"] < 1.50
            ],
        ),
    ):

        m = p23_metrics(rows)

        print(
            label,
            "| TRADES", m["trades"],
            "| WINS", m["wins"],
            "| LOSSES", m["losses"],
            "| EARLY_EXIT", m["early_exits"],
            "| AVG_PNL", round(m["avg_pnl"], 4), "%",
            "| TOTAL_PNL", round(m["total_pnl"], 4), "%",
            "| PF", round(m["pf"], 3),
        )

    # ------------------------------------------------
    # Walk-forward block comparison
    # ------------------------------------------------

    print("\nBLOCK STABILITY")

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

        print("\nBLOCK", block_idx + 1)

        variants_to_check = [
            ("BASELINE", p23_baseline_rows),
            ("C1_EXIT", p23_variants[1]),
            ("C2_EXIT", p23_variants[2]),
        ]

        for label, source_rows in variants_to_check:

            rows = [
                x for x in source_rows
                if x["event"]["dt"].date()
                in block_days
            ]

            m = p23_metrics(rows)

            print(
                label,
                "| TRADES", m["trades"],
                "| AVG_PNL", round(m["avg_pnl"], 4), "%",
                "| TOTAL_PNL", round(m["total_pnl"], 4), "%",
                "| PF", round(m["pf"], 3),
            )

    print("\nPART 23 COMPLETE")


    # ================================================================
    # PART 24 - RANGE_ATR UPPER CAP WALK-FORWARD VALIDATION
    # Frozen base entry: MID + RANGE_ATR >= 0.75
    # Candidate improvement: RANGE_ATR < 1.50
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 24 - RANGE_ATR UPPER CAP WALK-FORWARD VALIDATION")
    print("BASELINE: MID + RANGE_ATR >= 0.75")
    print("TEST RULE: MID + 0.75 <= RANGE_ATR < 1.50")
    print("OUTCOME: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("PURPOSE: VALIDATE WHETHER EXCLUDING RANGE_ATR >= 1.50 IS STABLE")
    print("RULE: SAME EXACT 5 CHRONOLOGICAL BLOCKS AS PART 18")
    print("=" * 120)

    p24_baseline_events = p18_candidate_events
    p24_capped_events = [
        e for e in p24_baseline_events
        if e["range_atr"] < 1.50
    ]

    p24_all_days = sorted(set(
        e["dt"].date()
        for e in (p15_trade_events["TRAIN"] + p15_trade_events["OOS"])
    ))

    p24_num_blocks = 5
    p24_day_count = len(p24_all_days)

    print(
        "BASELINE EVENTS", len(p24_baseline_events),
        "| CAPPED EVENTS", len(p24_capped_events),
        "| REMOVED", len(p24_baseline_events) - len(p24_capped_events),
    )

    p24_base_positive = 0
    p24_cap_positive = 0
    p24_base_pf_gt1 = 0
    p24_cap_pf_gt1 = 0

    for block_idx in range(p24_num_blocks):
        start_idx = block_idx * p24_day_count // p24_num_blocks
        end_idx = (block_idx + 1) * p24_day_count // p24_num_blocks

        block_days = set(p24_all_days[start_idx:end_idx])

        if not block_days:
            continue

        base_events = [
            e for e in p24_baseline_events
            if e["dt"].date() in block_days
        ]

        cap_events = [
            e for e in p24_capped_events
            if e["dt"].date() in block_days
        ]

        base_m = p16_metrics(base_events)
        cap_m = p16_metrics(cap_events)

        if base_m["avg_pnl"] > 0:
            p24_base_positive += 1
        if cap_m["avg_pnl"] > 0:
            p24_cap_positive += 1

        if base_m["pf"] > 1.0:
            p24_base_pf_gt1 += 1
        if cap_m["pf"] > 1.0:
            p24_cap_pf_gt1 += 1

        print("\nBLOCK", block_idx + 1)
        print(
            "PERIOD", min(block_days), "TO", max(block_days),
            "| DAYS", len(block_days),
        )
        print(
            "BASELINE",
            "| TRADES", base_m["trades"],
            "| WIN_RATE", round(base_m["win_rate"], 2), "%",
            "| AVG_PNL", round(base_m["avg_pnl"], 4), "%",
            "| TOTAL_PNL", round(base_m["total_pnl"], 4), "%",
            "| PF", round(base_m["pf"], 3),
        )
        print(
            "RANGE_LT_1.50",
            "| TRADES", cap_m["trades"],
            "| WIN_RATE", round(cap_m["win_rate"], 2), "%",
            "| AVG_PNL", round(cap_m["avg_pnl"], 4), "%",
            "| TOTAL_PNL", round(cap_m["total_pnl"], 4), "%",
            "| PF", round(cap_m["pf"], 3),
        )

    p24_base_all = p16_metrics(p24_baseline_events)
    p24_cap_all = p16_metrics(p24_capped_events)

    print("\nOVERALL COMPARISON")
    print(
        "BASELINE",
        "| TRADES", p24_base_all["trades"],
        "| WIN_RATE", round(p24_base_all["win_rate"], 2), "%",
        "| AVG_PNL", round(p24_base_all["avg_pnl"], 4), "%",
        "| TOTAL_PNL", round(p24_base_all["total_pnl"], 4), "%",
        "| PF", round(p24_base_all["pf"], 3),
    )
    print(
        "RANGE_LT_1.50",
        "| TRADES", p24_cap_all["trades"],
        "| WIN_RATE", round(p24_cap_all["win_rate"], 2), "%",
        "| AVG_PNL", round(p24_cap_all["avg_pnl"], 4), "%",
        "| TOTAL_PNL", round(p24_cap_all["total_pnl"], 4), "%",
        "| PF", round(p24_cap_all["pf"], 3),
    )

    print("\nBLOCK STABILITY SUMMARY")
    print(
        "BASELINE POSITIVE AVG_PNL", p24_base_positive, "/", p24_num_blocks,
        "| RANGE_LT_1.50", p24_cap_positive, "/", p24_num_blocks,
    )
    print(
        "BASELINE PF_GT_1", p24_base_pf_gt1, "/", p24_num_blocks,
        "| RANGE_LT_1.50", p24_cap_pf_gt1, "/", p24_num_blocks,
    )

    print("\nPART 24 COMPLETE")


    # ================================================================
    # PART 25 - HIGH WIN-RATE SIGNAL QUALITY DIAGNOSIS
    # Frozen candidate: MID + 0.75 <= RANGE_ATR < 1.50
    # Goal: identify robust existing setup confirmations
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 25 - HIGH WIN-RATE SIGNAL QUALITY DIAGNOSIS")
    print("FROZEN BASE: MID + 0.75 <= RANGE_ATR < 1.50")
    print("OUTCOME: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("GOAL: FIND EXISTING PRICE-ACTION CONFIRMATIONS WITH HIGHER WIN RATE")
    print("RULE: DIAGNOSIS ONLY - DO NOT OPTIMIZE USING OOS")
    print("=" * 120)

    p25_events = p24_capped_events

    def p25_print_metrics(label, events):
        m = p16_metrics(events)
        print(
            label,
            "| TRADES", m["trades"],
            "| WINS", m["wins"],
            "| LOSSES", m["losses"],
            "| TIME_EXIT", m["time_exits"],
            "| WIN_RATE", round(m["win_rate"], 2), "%",
            "| AVG_PNL", round(m["avg_pnl"], 4), "%",
            "| PF", round(m["pf"], 3),
        )

    print("\nTRAIN / OOS BASELINE")

    p25_train = [
        e for e in p25_events
        if e["dt"].date() in train_days
    ]
    p25_oos = [
        e for e in p25_events
        if e["dt"].date() in oos_days
    ]

    p25_print_metrics("TRAIN", p25_train)
    p25_print_metrics("OOS  ", p25_oos)

    print("\nEXISTING SETUP TAG DIAGNOSIS")

    p25_setup_names = sorted(set(
        setup
        for e in p25_events
        for setup in e.get("setups", ())
    ))

    print("SETUP TAGS FOUND:", p25_setup_names)

    for setup_name in p25_setup_names:
        train_subset = [
            e for e in p25_train
            if setup_name in e.get("setups", ())
        ]
        oos_subset = [
            e for e in p25_oos
            if setup_name in e.get("setups", ())
        ]

        print("\nSETUP", setup_name)
        p25_print_metrics("TRAIN", train_subset)
        p25_print_metrics("OOS  ", oos_subset)

    print("\nSETUP COUNT DIAGNOSIS")

    p25_setup_counts = sorted(set(
        len(e.get("setups", ()))
        for e in p25_events
    ))

    for min_count in p25_setup_counts:
        train_subset = [
            e for e in p25_train
            if len(e.get("setups", ())) >= min_count
        ]
        oos_subset = [
            e for e in p25_oos
            if len(e.get("setups", ())) >= min_count
        ]

        print("\nMIN_SETUP_COUNT >=", min_count)
        p25_print_metrics("TRAIN", train_subset)
        p25_print_metrics("OOS  ", oos_subset)

    print("\nPART 25 COMPLETE")


    # ================================================================
    # PART 26 - ONE-CANDLE DELAYED CONFIRMATION ENTRY
    # Frozen signal: MID + 0.75 <= RANGE_ATR < 1.50
    # Short/PE confirmation: first future candle closes below original entry
    # New entry: confirmation candle close
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 26 - ONE-CANDLE DELAYED CONFIRMATION ENTRY")
    print("FROZEN SIGNAL: MID + 0.75 <= RANGE_ATR < 1.50")
    print("CONFIRMATION: FIRST FUTURE CANDLE CLOSE < ORIGINAL ENTRY")
    print("NEW ENTRY: CONFIRMATION CANDLE CLOSE")
    print("OUTCOME: TARGET 0.12% | SL 0.10%")
    print("PURPOSE: TEST WHETHER WAITING FOR PRICE CONFIRMATION IMPROVES WIN RATE")
    print("=" * 120)

    p26_target = 0.12
    p26_stop = 0.10

    def p26_simulate(events):
        results = []
        rejected = 0
        no_future = 0

        for e in events:
            future = e["future"]

            if not future:
                no_future += 1
                continue

            confirm = future[0]

            if confirm["c"] >= e["entry"]:
                rejected += 1
                continue

            new_entry = confirm["c"]
            post_confirm_future = future[1:]

            if not post_confirm_future:
                no_future += 1
                continue

            result, pnl = p6_simulate_short(
                new_entry,
                post_confirm_future,
                p26_target,
                p26_stop,
            )

            results.append({
                "dt": e["dt"],
                "result": result,
                "pnl": pnl,
                "original_entry": e["entry"],
                "new_entry": new_entry,
            })

        return results, rejected, no_future

    def p26_metrics(results):
        trades = len(results)
        wins = sum(1 for x in results if x["result"] == "WIN")
        losses = sum(1 for x in results if x["result"] == "LOSS")
        time_exits = sum(1 for x in results if x["result"] == "TIME_EXIT")
        total_pnl = sum(x["pnl"] for x in results)
        avg_pnl = total_pnl / trades if trades else 0.0
        win_rate = 100.0 * wins / trades if trades else 0.0

        gross_profit = sum(
            x["pnl"] for x in results
            if x["pnl"] > 0
        )
        gross_loss = abs(sum(
            x["pnl"] for x in results
            if x["pnl"] < 0
        ))
        pf = gross_profit / gross_loss if gross_loss else 0.0

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

    p26_train_events = [
        e for e in p25_events
        if e["dt"].date() in train_days
    ]
    p26_oos_events = [
        e for e in p25_events
        if e["dt"].date() in oos_days
    ]

    p26_train_results, p26_train_rejected, p26_train_no_future = p26_simulate(
        p26_train_events
    )
    p26_oos_results, p26_oos_rejected, p26_oos_no_future = p26_simulate(
        p26_oos_events
    )

    p26_all_results = p26_train_results + p26_oos_results

    print("\nTRAIN / OOS RESULTS")

    for label, source_events, results, rejected, no_future in (
        ("TRAIN", p26_train_events, p26_train_results, p26_train_rejected, p26_train_no_future),
        ("OOS", p26_oos_events, p26_oos_results, p26_oos_rejected, p26_oos_no_future),
    ):
        m = p26_metrics(results)
        print(
            label,
            "| SIGNALS", len(source_events),
            "| CONFIRMED", m["trades"],
            "| REJECTED", rejected,
            "| NO_FUTURE", no_future,
            "| WINS", m["wins"],
            "| LOSSES", m["losses"],
            "| TIME_EXIT", m["time_exits"],
            "| WIN_RATE", round(m["win_rate"], 2), "%",
            "| AVG_PNL", round(m["avg_pnl"], 4), "%",
            "| TOTAL_PNL", round(m["total_pnl"], 4), "%",
            "| PF", round(m["pf"], 3),
        )

    p26_all_m = p26_metrics(p26_all_results)

    print("\nOVERALL CONFIRMED ENTRY RESULT")
    print(
        "TRADES", p26_all_m["trades"],
        "| WINS", p26_all_m["wins"],
        "| LOSSES", p26_all_m["losses"],
        "| TIME_EXIT", p26_all_m["time_exits"],
        "| WIN_RATE", round(p26_all_m["win_rate"], 2), "%",
        "| AVG_PNL", round(p26_all_m["avg_pnl"], 4), "%",
        "| TOTAL_PNL", round(p26_all_m["total_pnl"], 4), "%",
        "| PF", round(p26_all_m["pf"], 3),
    )

    print("\nPART 26 COMPLETE")


    # ================================================================
    # PART 27 - PRE-ENTRY PRICE-ACTION FEATURE DIAGNOSIS
    # Frozen base: MID + 0.75 <= RANGE_ATR < 1.50
    # Only information available before/at confirmed entry is tested.
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 27 - PRE-ENTRY PRICE-ACTION FEATURE DIAGNOSIS")
    print("FROZEN BASE: MID + 0.75 <= RANGE_ATR < 1.50")
    print("OUTCOME: TARGET 0.12% | SL 0.10% | HORIZON 5 CANDLES")
    print("PURPOSE: FIND FEATURES PRESENT BEFORE ENTRY THAT SEPARATE WINNERS FROM LOSERS")
    print("RULE: TRAIN/OOS REPORTED SEPARATELY - NO FUTURE FEATURE USED")
    print("=" * 120)

    p27_events = p24_capped_events
    p27_feature_names = (
        "PRIOR_UP_5",
        "BEARISH_ENGULF",
        "CLOSE_NEAR_LOW",
        "EMA_BREAK",
        "EMA_REJECTION",
        "MOMENTUM_DOWN",
        "EMA_BEAR",
        "BREAK_PREV_LOW",
    )

    def p27_outcome(e):
        return p6_simulate_short(
            e["entry"],
            e["future"],
            0.12,
            0.10,
        )[0]

    def p27_report(label, events):
        total = len(events)
        wins = sum(1 for e in events if p27_outcome(e) == "WIN")
        losses = sum(1 for e in events if p27_outcome(e) == "LOSS")
        time_exits = total - wins - losses
        wr = 100.0 * wins / total if total else 0.0
        print(
            label,
            "| TRADES", total,
            "| WINS", wins,
            "| LOSSES", losses,
            "| TIME_EXIT", time_exits,
            "| WIN_RATE", round(wr, 2), "%",
        )

    p27_train = [
        e for e in p27_events
        if e["dt"].date() in train_days
    ]
    p27_oos = [
        e for e in p27_events
        if e["dt"].date() in oos_days
    ]

    print("\nBASELINE")
    p27_report("TRAIN", p27_train)
    p27_report("OOS  ", p27_oos)

    print("\nSINGLE FEATURE PRESENCE")

    for feature_name in p27_feature_names:
        train_yes = [
            e for e in p27_train
            if e.get("features", {}).get(feature_name, False)
        ]
        oos_yes = [
            e for e in p27_oos
            if e.get("features", {}).get(feature_name, False)
        ]

        print("\nFEATURE", feature_name)
        p27_report("TRAIN", train_yes)
        p27_report("OOS  ", oos_yes)

    print("\nFEATURE ABSENCE")

    for feature_name in p27_feature_names:
        train_no = [
            e for e in p27_train
            if not e.get("features", {}).get(feature_name, False)
        ]
        oos_no = [
            e for e in p27_oos
            if not e.get("features", {}).get(feature_name, False)
        ]

        print("\nWITHOUT", feature_name)
        p27_report("TRAIN", train_no)
        p27_report("OOS  ", oos_no)

    print("\nPART 27 COMPLETE")


    # ================================================================
    # PART 28 - CPR / CLASSIC PIVOT LOCATION DIAGNOSIS
    # Levels use PREVIOUS TRADING DAY OHLC only.
    # No future information is used.
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 28 - CPR / CLASSIC PIVOT LOCATION DIAGNOSIS")
    print("FROZEN BASE: MID + 0.75 <= RANGE_ATR < 1.50")
    print("LEVEL SOURCE: PREVIOUS TRADING DAY HIGH / LOW / CLOSE")
    print("ENTRY LOCATION: CONFIRMED ENTRY PRICE")
    print("PURPOSE: FIND WHETHER PE REVERSAL QUALITY DEPENDS ON CPR / PIVOT LOCATION")
    print("RULE: TRAIN/OOS SEPARATE - NO FUTURE DATA")
    print("=" * 120)

    p28_events = p24_capped_events

    # Build daily OHLC from existing intraday candles.
    p28_daily = {}
    for x in candles:
        d = x["dt"].date()
        if d not in p28_daily:
            p28_daily[d] = {
                "h": x["h"],
                "l": x["l"],
                "c": x["c"],
            }
        else:
            p28_daily[d]["h"] = max(p28_daily[d]["h"], x["h"])
            p28_daily[d]["l"] = min(p28_daily[d]["l"], x["l"])
            p28_daily[d]["c"] = x["c"]

    p28_days = sorted(p28_daily)
    p28_prev_day = {
        p28_days[i]: p28_days[i - 1]
        for i in range(1, len(p28_days))
    }

    def p28_levels(trade_day):
        prev_day = p28_prev_day.get(trade_day)
        if prev_day is None:
            return None

        prev = p28_daily[prev_day]
        h = prev["h"]
        l = prev["l"]
        c = prev["c"]

        pivot = (h + l + c) / 3.0
        bc_raw = (h + l) / 2.0
        tc_raw = 2.0 * pivot - bc_raw
        bc = min(bc_raw, tc_raw)
        tc = max(bc_raw, tc_raw)

        r1 = 2.0 * pivot - l
        s1 = 2.0 * pivot - h
        r2 = pivot + (h - l)
        s2 = pivot - (h - l)
        r3 = h + 2.0 * (pivot - l)
        s3 = l - 2.0 * (h - pivot)

        return {
            "S3": s3,
            "S2": s2,
            "S1": s1,
            "BC": bc,
            "PIVOT": pivot,
            "TC": tc,
            "R1": r1,
            "R2": r2,
            "R3": r3,
        }

    def p28_zone(price, lv):
        if price < lv["S3"]:
            return "BELOW_S3"
        if price < lv["S2"]:
            return "S3_TO_S2"
        if price < lv["S1"]:
            return "S2_TO_S1"
        if price < lv["BC"]:
            return "S1_TO_BC"
        if price <= lv["TC"]:
            return "INSIDE_CPR"
        if price <= lv["R1"]:
            return "TC_TO_R1"
        if price <= lv["R2"]:
            return "R1_TO_R2"
        if price <= lv["R3"]:
            return "R2_TO_R3"
        return "ABOVE_R3"

    p28_details = []
    for e in p28_events:
        lv = p28_levels(e["dt"].date())
        if lv is None:
            continue

        price = e["confirm_close"]
        x = dict(e)
        x["pivot_levels"] = lv
        x["pivot_zone"] = p28_zone(price, lv)
        p28_details.append(x)

    p28_train = [
        e for e in p28_details
        if e["dt"].date() in train_days
    ]
    p28_oos = [
        e for e in p28_details
        if e["dt"].date() in oos_days
    ]

    def p28_report(label, events):
        m = p16_metrics(events)
        print(
            label,
            "| TRADES", m["trades"],
            "| WINS", m["wins"],
            "| LOSSES", m["losses"],
            "| TIME_EXIT", m["time_exits"],
            "| WIN_RATE", round(m["win_rate"], 2), "%",
            "| AVG_PNL", round(m["avg_pnl"], 4), "%",
            "| PF", round(m["pf"], 3),
        )

    print("\nBASELINE WITH VALID PREVIOUS-DAY LEVELS")
    p28_report("TRAIN", p28_train)
    p28_report("OOS  ", p28_oos)

    print("\nPIVOT / CPR LOCATION ZONES")

    p28_zone_order = (
        "BELOW_S3",
        "S3_TO_S2",
        "S2_TO_S1",
        "S1_TO_BC",
        "INSIDE_CPR",
        "TC_TO_R1",
        "R1_TO_R2",
        "R2_TO_R3",
        "ABOVE_R3",
    )

    for zone in p28_zone_order:
        train_subset = [e for e in p28_train if e["pivot_zone"] == zone]
        oos_subset = [e for e in p28_oos if e["pivot_zone"] == zone]

        if not train_subset and not oos_subset:
            continue

        print("\nZONE", zone)
        p28_report("TRAIN", train_subset)
        p28_report("OOS  ", oos_subset)

    print("\nBROAD CPR LOCATION")

    p28_broad_tests = (
        ("BELOW_CPR", lambda e: e["confirm_close"] < e["pivot_levels"]["BC"]),
        ("INSIDE_CPR", lambda e: e["pivot_levels"]["BC"] <= e["confirm_close"] <= e["pivot_levels"]["TC"]),
        ("ABOVE_CPR", lambda e: e["confirm_close"] > e["pivot_levels"]["TC"]),
        ("AT_OR_ABOVE_R1", lambda e: e["confirm_close"] >= e["pivot_levels"]["R1"]),
        ("AT_OR_BELOW_S1", lambda e: e["confirm_close"] <= e["pivot_levels"]["S1"]),
    )

    for name, condition in p28_broad_tests:
        train_subset = [e for e in p28_train if condition(e)]
        oos_subset = [e for e in p28_oos if condition(e)]

        print("\nLOCATION", name)
        p28_report("TRAIN", train_subset)
        p28_report("OOS  ", oos_subset)

    print("\nPART 28 COMPLETE")


    # ================================================================
    # PART 29 - NIFTY FUTURES VWAP EXPLORATORY DIAGNOSIS
    # July 2026 front-month futures only.
    # True session VWAP uses actual futures volume.
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 29 - NIFTY FUTURES VWAP EXPLORATORY DIAGNOSIS")
    print("FROZEN SPOT SIGNAL: MID + 0.75 <= RANGE_ATR < 1.50")
    print("FUTURES: NIFTY26JULFUT | TOKEN 61093 | SEGMENT NFO")
    print("VWAP: SESSION RESET | TYPICAL PRICE * ACTUAL FUTURES VOLUME")
    print("WINDOW: 2026-07-01 TO 2026-07-20")
    print("PURPOSE: EXPLORATORY TEST ONLY - NOT FINAL WALK-FORWARD VALIDATION")
    print("=" * 120)

    p29_token = open(TOKEN_FILE).read().strip()
    p29_api = MConnect(
        api_key=API_KEY,
        access_Token=p29_token,
    )

    p29_response = p29_api.get_historical_chart(
        "NFO",
        "61093",
        "5minute",
        "2026-07-01",
        "2026-07-20",
    )

    try:
        p29_raw = (
            p29_response.json()
            .get("data", {})
            .get("candles")
            or []
        )
    except Exception as exc:
        print("PART29 FUTURES FETCH ERROR", type(exc).__name__, exc)
        p29_raw = []

    p29_futures = []
    for row in p29_raw:
        try:
            if len(row) < 6:
                continue
            p29_futures.append({
                "dt": datetime.fromisoformat(str(row[0])),
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[5]),
            })
        except Exception:
            continue

    p29_futures.sort(key=lambda x: x["dt"])

    # Calculate true intraday session VWAP.
    p29_by_time = {}
    p29_current_day = None
    p29_cum_pv = 0.0
    p29_cum_v = 0.0
    p29_prev = None

    for x in p29_futures:
        day = x["dt"].date()

        if day != p29_current_day:
            p29_current_day = day
            p29_cum_pv = 0.0
            p29_cum_v = 0.0
            p29_prev = None

        typical = (x["h"] + x["l"] + x["c"]) / 3.0
        p29_cum_pv += typical * x["v"]
        p29_cum_v += x["v"]

        if p29_cum_v <= 0:
            continue

        vwap = p29_cum_pv / p29_cum_v

        x["vwap"] = vwap
        x["prev_close"] = p29_prev["c"] if p29_prev else None
        x["prev_vwap"] = p29_prev["vwap"] if p29_prev else None

        p29_by_time[x["dt"]] = x
        p29_prev = x

    print(
        "FUTURES CANDLES", len(p29_futures),
        "| VWAP TIMESTAMPS", len(p29_by_time),
    )

    p29_details = []

    for e in p24_capped_events:
        fut = p29_by_time.get(e["dt"])
        if fut is None:
            continue

        x = dict(e)
        x["fut_close"] = fut["c"]
        x["fut_high"] = fut["h"]
        x["fut_low"] = fut["l"]
        x["fut_vwap"] = fut["vwap"]
        x["vwap_distance_pct"] = (
            (fut["c"] - fut["vwap"])
            / fut["vwap"]
            * 100.0
        )
        x["below_vwap"] = fut["c"] < fut["vwap"]
        x["above_vwap"] = fut["c"] > fut["vwap"]
        x["vwap_rejection"] = (
            fut["h"] >= fut["vwap"]
            and fut["c"] < fut["vwap"]
        )
        x["vwap_breakdown"] = (
            fut["prev_close"] is not None
            and fut["prev_vwap"] is not None
            and fut["prev_close"] >= fut["prev_vwap"]
            and fut["c"] < fut["vwap"]
        )
        p29_details.append(x)

    def p29_report(label, events):
        m29 = p16_metrics(events)
        print(
            label,
            "| TRADES", m29["trades"],
            "| WINS", m29["wins"],
            "| LOSSES", m29["losses"],
            "| TIME_EXIT", m29["time_exits"],
            "| WIN_RATE", round(m29["win_rate"], 2), "%",
            "| AVG_PNL", round(m29["avg_pnl"], 4), "%",
            "| PF", round(m29["pf"], 3),
        )

    print("\nMATCHED JULY SIGNALS")
    p29_report("ALL", p29_details)

    p29_tests = (
        ("BELOW_VWAP", lambda e: e["below_vwap"]),
        ("ABOVE_VWAP", lambda e: e["above_vwap"]),
        ("VWAP_REJECTION", lambda e: e["vwap_rejection"]),
        ("VWAP_BREAKDOWN", lambda e: e["vwap_breakdown"]),
        ("BELOW_VWAP_0.05_PLUS", lambda e: e["vwap_distance_pct"] <= -0.05),
        ("BELOW_VWAP_0.10_PLUS", lambda e: e["vwap_distance_pct"] <= -0.10),
        ("NEAR_VWAP_0.05", lambda e: abs(e["vwap_distance_pct"]) <= 0.05),
        ("ABOVE_VWAP_0.05_PLUS", lambda e: e["vwap_distance_pct"] >= 0.05),
    )

    print("\nVWAP STATE DIAGNOSIS")

    for name, condition in p29_tests:
        subset = [e for e in p29_details if condition(e)]
        print("\nSTATE", name)
        p29_report("RESULT", subset)

    print("\nVWAP DISTANCE BUCKETS")

    p29_buckets = (
        ("BELOW_MORE_THAN_0.10", lambda d: d < -0.10),
        ("BELOW_0.05_TO_0.10", lambda d: -0.10 <= d < -0.05),
        ("NEAR_MINUS_0.05_TO_0", lambda d: -0.05 <= d < 0.0),
        ("NEAR_0_TO_PLUS_0.05", lambda d: 0.0 <= d <= 0.05),
        ("ABOVE_0.05_TO_0.10", lambda d: 0.05 < d <= 0.10),
        ("ABOVE_MORE_THAN_0.10", lambda d: d > 0.10),
    )

    for name, condition in p29_buckets:
        subset = [
            e for e in p29_details
            if condition(e["vwap_distance_pct"])
        ]
        if not subset:
            continue
        print("\nBUCKET", name)
        p29_report("RESULT", subset)

    print("\nPART 29 COMPLETE")


    # ================================================================
    # PART 30 - VWAP STRETCH + PRE-ENTRY REVERSAL DIAGNOSIS
    # Uses only July events matched to real NIFTY futures VWAP.
    # Exploratory only due to small sample size.
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 30 - VWAP STRETCH + PRE-ENTRY REVERSAL DIAGNOSIS")
    print("BASE: PART 29 MATCHED JULY SIGNALS")
    print("PURPOSE: TEST WHETHER PE REVERSALS WORK BETTER WHEN FUTURES ARE STRETCHED ABOVE VWAP")
    print("RULE: PRE-ENTRY FEATURES ONLY | EXPLORATORY | NO FINAL FILTER SELECTION")
    print("=" * 120)

    p30_events = p29_details

    def p30_report(label, events):
        m30 = p16_metrics(events)
        print(
            label,
            "| TRADES", m30["trades"],
            "| WINS", m30["wins"],
            "| LOSSES", m30["losses"],
            "| TIME_EXIT", m30["time_exits"],
            "| WIN_RATE", round(m30["win_rate"], 2), "%",
            "| AVG_PNL", round(m30["avg_pnl"], 4), "%",
            "| PF", round(m30["pf"], 3),
        )

    print("\nBASELINE")
    p30_report("ALL", p30_events)

    p30_stretches = (
        ("ABOVE_VWAP", lambda e: e["vwap_distance_pct"] > 0.0),
        ("ABOVE_0.05", lambda e: e["vwap_distance_pct"] >= 0.05),
        ("ABOVE_0.10", lambda e: e["vwap_distance_pct"] >= 0.10),
    )

    p30_features = (
        "PRIOR_UP_5",
        "BEARISH_ENGULF",
        "CLOSE_NEAR_LOW",
        "EMA_BREAK",
        "EMA_REJECTION",
        "MOMENTUM_DOWN",
        "EMA_BEAR",
        "BREAK_PREV_LOW",
    )

    print("\nVWAP STRETCH BASELINES")
    for stretch_name, stretch_condition in p30_stretches:
        subset = [e for e in p30_events if stretch_condition(e)]
        print("\nSTRETCH", stretch_name)
        p30_report("RESULT", subset)

    print("\nVWAP STRETCH + FEATURE PRESENCE")

    for stretch_name, stretch_condition in p30_stretches:
        print("\n---", stretch_name, "---")

        for feature_name in p30_features:
            subset = [
                e for e in p30_events
                if stretch_condition(e)
                and e.get("features", {}).get(feature_name, False)
            ]

            if not subset:
                continue

            print("FEATURE", feature_name)
            p30_report("RESULT", subset)

    print("\nVWAP STRETCH + FEATURE ABSENCE")

    for stretch_name, stretch_condition in p30_stretches:
        print("\n---", stretch_name, "---")

        for feature_name in p30_features:
            subset = [
                e for e in p30_events
                if stretch_condition(e)
                and not e.get("features", {}).get(feature_name, False)
            ]

            if not subset:
                continue

            print("WITHOUT", feature_name)
            p30_report("RESULT", subset)

    print("\nPART 30 COMPLETE")


    # ================================================================



    # ================================================================
    # PART 31 - VWAP STRETCH + EMA / MOMENTUM COMBINATION DIAGNOSTIC
    # ================================================================

    print("\n" + "=" * 120)
    print("PART 31 - VWAP STRETCH + EMA / MOMENTUM COMBINATION DIAGNOSTIC")
    print("BASE: PART 30 MATCHED JULY SIGNALS")
    print("PURPOSE: TEST VWAP STRETCH WITH EMA + MOMENTUM REVERSAL COMBINATIONS")
    print("RULE: PRE-ENTRY FEATURES ONLY | EXPLORATORY | NO FINAL FILTER SELECTION")
    print("=" * 120)

    p31_events = p29_details

    p31_conditions = (
        (
            "ABOVE_VWAP + EMA_BREAK + MOMENTUM_DOWN",
            lambda e: (
                e["above_vwap"]
                and e.get("features", {}).get("EMA_BREAK", False)
                and e.get("features", {}).get("MOMENTUM_DOWN", False)
            ),
        ),
        (
            "ABOVE_VWAP + EMA_REJECTION + MOMENTUM_DOWN",
            lambda e: (
                e["above_vwap"]
                and e.get("features", {}).get("EMA_REJECTION", False)
                and e.get("features", {}).get("MOMENTUM_DOWN", False)
            ),
        ),
        (
            "ABOVE_0.05 + EMA_BREAK + MOMENTUM_DOWN",
            lambda e: (
                e["vwap_distance_pct"] >= 0.05
                and e.get("features", {}).get("EMA_BREAK", False)
                and e.get("features", {}).get("MOMENTUM_DOWN", False)
            ),
        ),
        (
            "ABOVE_0.05 + EMA_REJECTION + MOMENTUM_DOWN",
            lambda e: (
                e["vwap_distance_pct"] >= 0.05
                and e.get("features", {}).get("EMA_REJECTION", False)
                and e.get("features", {}).get("MOMENTUM_DOWN", False)
            ),
        ),
        (
            "ABOVE_VWAP + EMA_BREAK",
            lambda e: (
                e["above_vwap"]
                and e.get("features", {}).get("EMA_BREAK", False)
            ),
        ),
        (
            "ABOVE_VWAP + MOMENTUM_DOWN",
            lambda e: (
                e["above_vwap"]
                and e.get("features", {}).get("MOMENTUM_DOWN", False)
            ),
        ),
    )

    print("\nCOMBINATION RESULTS")

    for name, condition in p31_conditions:
        subset = [
            e for e in p31_events
            if condition(e)
        ]

        print("\nCOMBO", name)
        p30_report("RESULT", subset)

    print("\nPART 31 COMPLETE")

if __name__ == "__main__":
    part10_main()

