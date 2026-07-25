import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY


TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"

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

MAX_CANDLES = 5000
INTERVAL = "5minute"
CHUNK_DAYS = 7

# Spot-index percentage targets.
# Multiple target/SL pairs tested in the same run.
TARGET_SL_MATRIX = [
    (0.05, 0.05),
    (0.08, 0.05),
    (0.10, 0.05),
    (0.10, 0.08),
    (0.10, 0.10),
    (0.15, 0.10),
    (0.20, 0.10),
]

FORWARD_WINDOWS = [3, 5, 10, 15]


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
        data.get("data", {}).get("candles", [])
        or []
    )


def fetch_chunk(
    m,
    segment,
    token,
    interval,
    from_date,
    to_date,
):
    response = m.get_historical_chart(
        segment,
        str(token),
        interval,
        from_date,
        to_date,
    )

    return get_candles(response)


def fetch_large_history(
    m,
    segment,
    token,
    interval,
    chunk_days,
    max_candles=5000,
):
    all_rows = []

    cursor_end = datetime.now()

    loops = 0
    max_loops = 300

    while (
        len(all_rows) < max_candles
        and loops < max_loops
    ):
        loops += 1

        cursor_start = (
            cursor_end
            - timedelta(days=chunk_days)
        )

        try:
            rows = fetch_chunk(
                m,
                segment,
                token,
                interval,
                cursor_start.strftime("%Y-%m-%d"),
                cursor_end.strftime("%Y-%m-%d"),
            )

        except Exception as e:
            print(
                "LARGE HISTORY FETCH ERROR",
                interval,
                cursor_start.strftime("%Y-%m-%d"),
                cursor_end.strftime("%Y-%m-%d"),
                type(e).__name__,
                e,
            )

            rows = []

        if rows:
            all_rows.extend(rows)

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
        key=lambda x: x[0],
    )

    if len(rows) > max_candles:
        rows = rows[-max_candles:]

    return rows


def parse_time(value):
    text = str(value)

    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                text,
                fmt,
            )
        except Exception:
            pass

    # Handles ISO timestamps with timezone offsets
    try:
        return datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )
    except Exception:
        return None


def normalize_rows(rows):
    candles = []

    for row in rows:
        if not row or len(row) < 5:
            continue

        dt = parse_time(row[0])

        if dt is None:
            continue

        try:
            candle = {
                "time": dt,
                "date": dt.date(),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": (
                    float(row[5])
                    if len(row) > 5
                    and row[5] is not None
                    else 0.0
                ),
            }

        except Exception:
            continue

        candles.append(candle)

    candles.sort(
        key=lambda x: x["time"]
    )

    return candles


def group_by_day(candles):
    grouped = defaultdict(list)

    for candle in candles:
        grouped[candle["date"]].append(
            candle
        )

    for day in grouped:
        grouped[day].sort(
            key=lambda x: x["time"]
        )

    return dict(
        sorted(grouped.items())
    )


def pct_move(a, b):
    if not a:
        return 0.0

    return (
        (b - a)
        / a
        * 100.0
    )


def previous_day_context(day):
    if not day:
        return None

    return {
        "open": day[0]["open"],
        "high": max(
            x["high"]
            for x in day
        ),
        "low": min(
            x["low"]
            for x in day
        ),
        "close": day[-1]["close"],
    }


def first_n_range(day, n):
    subset = day[:n]

    if not subset:
        return None

    return {
        "high": max(
            x["high"]
            for x in subset
        ),
        "low": min(
            x["low"]
            for x in subset
        ),
        "open": subset[0]["open"],
        "close": subset[-1]["close"],
    }


def add_signal(
    signals,
    rule,
    direction,
    index,
    day,
):
    if index < 0:
        return

    if index >= len(day):
        return

    signals.append(
        {
            "rule": rule,
            "direction": direction,
            "index": index,
            "time": day[index]["time"],
            "entry": day[index]["close"],
        }
    )


def generate_day_signals(
    day,
    prev,
):
    signals = []

    if len(day) < 8:
        return signals

    pdh = prev["high"]
    pdl = prev["low"]
    pdc = prev["close"]
    prev_range = pdh - pdl

    day_open = day[0]["open"]

    gap_pct = pct_move(
        pdc,
        day_open,
    )

    # --------------------------------------------------
    # 1. GAP BEHAVIOR
    # --------------------------------------------------

    if gap_pct >= 0.10:
        add_signal(
            signals,
            "GAP_UP_OPEN",
            "BULLISH",
            0,
            day,
        )

    if gap_pct <= -0.10:
        add_signal(
            signals,
            "GAP_DOWN_OPEN",
            "BEARISH",
            0,
            day,
        )

    # Gap continuation / reversal during first 30 min
    for i in range(
        1,
        min(6, len(day)),
    ):
        c = day[i]

        if gap_pct >= 0.10:
            if c["close"] > day_open:
                add_signal(
                    signals,
                    "GAP_UP_CONTINUATION",
                    "BULLISH",
                    i,
                    day,
                )
                break

        if gap_pct <= -0.10:
            if c["close"] < day_open:
                add_signal(
                    signals,
                    "GAP_DOWN_CONTINUATION",
                    "BEARISH",
                    i,
                    day,
                )
                break

    for i in range(
        1,
        min(8, len(day)),
    ):
        c = day[i]

        if gap_pct > 0:
            if c["close"] < pdc:
                add_signal(
                    signals,
                    "GAP_UP_FULL_REVERSAL",
                    "BEARISH",
                    i,
                    day,
                )
                break

        if gap_pct < 0:
            if c["close"] > pdc:
                add_signal(
                    signals,
                    "GAP_DOWN_FULL_RECOVERY",
                    "BULLISH",
                    i,
                    day,
                )
                break

    # --------------------------------------------------
    # 2. PREVIOUS DAY HIGH / LOW BREAK
    # --------------------------------------------------

    for i in range(1, len(day)):
        prev_c = day[i - 1]
        c = day[i]

        if (
            prev_c["close"] <= pdh
            and c["close"] > pdh
        ):
            add_signal(
                signals,
                "PDH_BREAKOUT",
                "BULLISH",
                i,
                day,
            )
            break

    for i in range(1, len(day)):
        prev_c = day[i - 1]
        c = day[i]

        if (
            prev_c["close"] >= pdl
            and c["close"] < pdl
        ):
            add_signal(
                signals,
                "PDL_BREAKDOWN",
                "BEARISH",
                i,
                day,
            )
            break

    # --------------------------------------------------
    # 3. PDH / PDL REJECTION
    # --------------------------------------------------

    for i, c in enumerate(day):

        if (
            c["high"] >= pdh
            and c["close"] < pdh
            and c["close"] < c["open"]
        ):
            add_signal(
                signals,
                "PDH_REJECTION",
                "BEARISH",
                i,
                day,
            )
            break

    for i, c in enumerate(day):

        if (
            c["low"] <= pdl
            and c["close"] > pdl
            and c["close"] > c["open"]
        ):
            add_signal(
                signals,
                "PDL_REJECTION",
                "BULLISH",
                i,
                day,
            )
            break

    # --------------------------------------------------
    # 4. PDH / PDL RECLAIM
    # --------------------------------------------------

    went_above_pdh = False

    for i, c in enumerate(day):

        if c["high"] > pdh:
            went_above_pdh = True

        if (
            went_above_pdh
            and c["close"] < pdh
        ):
            add_signal(
                signals,
                "PDH_FAILED_BREAK",
                "BEARISH",
                i,
                day,
            )
            break

    went_below_pdl = False

    for i, c in enumerate(day):

        if c["low"] < pdl:
            went_below_pdl = True

        if (
            went_below_pdl
            and c["close"] > pdl
        ):
            add_signal(
                signals,
                "PDL_FAILED_BREAK",
                "BULLISH",
                i,
                day,
            )
            break

    # --------------------------------------------------
    # 5. OPENING RANGE 5 / 15 / 30 MIN
    # --------------------------------------------------

    opening_ranges = [
        ("OR5", 1),
        ("OR15", 3),
        ("OR30", 6),
    ]

    for name, n in opening_ranges:

        if len(day) <= n:
            continue

        opening = first_n_range(
            day,
            n,
        )

        or_high = opening["high"]
        or_low = opening["low"]

        for i in range(
            n,
            len(day),
        ):
            if day[i]["close"] > or_high:
                add_signal(
                    signals,
                    name + "_BREAKOUT",
                    "BULLISH",
                    i,
                    day,
                )
                break

        for i in range(
            n,
            len(day),
        ):
            if day[i]["close"] < or_low:
                add_signal(
                    signals,
                    name + "_BREAKDOWN",
                    "BEARISH",
                    i,
                    day,
                )
                break

    # --------------------------------------------------
    # 6. OPENING DISPLACEMENT
    # --------------------------------------------------

    displacement_windows = [
        ("DISP_5M", 1),
        ("DISP_15M", 3),
        ("DISP_30M", 6),
    ]

    for name, n in displacement_windows:

        if len(day) < n:
            continue

        move = pct_move(
            day_open,
            day[n - 1]["close"],
        )

        if move >= 0.10:
            add_signal(
                signals,
                name,
                "BULLISH",
                n - 1,
                day,
            )

        elif move <= -0.10:
            add_signal(
                signals,
                name,
                "BEARISH",
                n - 1,
                day,
            )

    # --------------------------------------------------
    # 7. FAST PRICE VELOCITY
    # 2-candle and 3-candle directional displacement
    # --------------------------------------------------

    for window in (2, 3):

        for i in range(
            window,
            len(day),
        ):
            start = day[
                i - window
            ]["close"]

            end = day[i]["close"]

            move = pct_move(
                start,
                end,
            )

            if move >= 0.10:
                add_signal(
                    signals,
                    f"VELOCITY_{window}C",
                    "BULLISH",
                    i,
                    day,
                )
                break

            if move <= -0.10:
                add_signal(
                    signals,
                    f"VELOCITY_{window}C",
                    "BEARISH",
                    i,
                    day,
                )
                break

    # --------------------------------------------------
    # 8. PREVIOUS-DAY RANGE POSITION
    # --------------------------------------------------

    if prev_range > 0:

        for i, c in enumerate(day):

            position = (
                (c["close"] - pdl)
                / prev_range
            )

            if position >= 1.05:
                add_signal(
                    signals,
                    "ABOVE_PDH_EXPANSION",
                    "BULLISH",
                    i,
                    day,
                )
                break

        for i, c in enumerate(day):

            position = (
                (c["close"] - pdl)
                / prev_range
            )

            if position <= -0.05:
                add_signal(
                    signals,
                    "BELOW_PDL_EXPANSION",
                    "BEARISH",
                    i,
                    day,
                )
                break

    # --------------------------------------------------
    # 9. OPENING HIGH / LOW PROGRESSION
    # Pure price behavior, no indicator.
    # --------------------------------------------------

    for i in range(
        2,
        len(day),
    ):

        a = day[i - 2]
        b = day[i - 1]
        c = day[i]

        if (
            c["high"] > b["high"] > a["high"]
            and
            c["low"] > b["low"] > a["low"]
        ):
            add_signal(
                signals,
                "HH_HL_3C",
                "BULLISH",
                i,
                day,
            )
            break

    for i in range(
        2,
        len(day),
    ):

        a = day[i - 2]
        b = day[i - 1]
        c = day[i]

        if (
            c["high"] < b["high"] < a["high"]
            and
            c["low"] < b["low"] < a["low"]
        ):
            add_signal(
                signals,
                "LH_LL_3C",
                "BEARISH",
                i,
                day,
            )
            break

    # --------------------------------------------------
    # 10. STRONG SINGLE-CANDLE DISPLACEMENT
    # --------------------------------------------------

    for i, c in enumerate(day):

        move = pct_move(
            c["open"],
            c["close"],
        )

        if move >= 0.10:
            add_signal(
                signals,
                "STRONG_CANDLE_DISPLACEMENT",
                "BULLISH",
                i,
                day,
            )
            break

        if move <= -0.10:
            add_signal(
                signals,
                "STRONG_CANDLE_DISPLACEMENT",
                "BEARISH",
                i,
                day,
            )
            break

    # Remove exact duplicate rule/direction/index
    unique = {}

    for signal in signals:
        key = (
            signal["rule"],
            signal["direction"],
            signal["index"],
        )

        unique[key] = signal

    return list(
        unique.values()
    )


def target_before_stop(
    day,
    entry_index,
    direction,
    target_pct,
    stop_pct,
    forward_window,
):
    if entry_index >= len(day):
        return "NONE"

    entry = day[
        entry_index
    ]["close"]

    if direction == "BULLISH":

        target = entry * (
            1
            + target_pct / 100
        )

        stop = entry * (
            1
            - stop_pct / 100
        )

    else:

        target = entry * (
            1
            - target_pct / 100
        )

        stop = entry * (
            1
            + stop_pct / 100
        )

    end_index = min(
        len(day),
        entry_index
        + forward_window
        + 1,
    )

    for i in range(
        entry_index + 1,
        end_index,
    ):

        c = day[i]

        if direction == "BULLISH":

            hit_target = (
                c["high"] >= target
            )

            hit_stop = (
                c["low"] <= stop
            )

        else:

            hit_target = (
                c["low"] <= target
            )

            hit_stop = (
                c["high"] >= stop
            )

        # If both touched in same 5m candle,
        # order is unknowable from OHLC.
        # Count conservatively as STOP.
        if hit_target and hit_stop:
            return "S"

        if hit_target:
            return "T"

        if hit_stop:
            return "S"

    return "NONE"


def move_capture_stats(
    day,
    signal,
):
    i = signal["index"]
    entry = signal["entry"]
    direction = signal["direction"]

    future = day[i:]

    if not future:
        return 0.0, 0.0

    if direction == "BULLISH":

        best = max(
            x["high"]
            for x in future
        )

        worst = min(
            x["low"]
            for x in future
        )

        mfe = pct_move(
            entry,
            best,
        )

        mae = abs(
            pct_move(
                entry,
                worst,
            )
        )

    else:

        best = min(
            x["low"]
            for x in future
        )

        worst = max(
            x["high"]
            for x in future
        )

        mfe = abs(
            pct_move(
                entry,
                best,
            )
        )

        mae = abs(
            pct_move(
                entry,
                worst,
            )
        )

    return mfe, mae


def research_index(
    api,
    index_name,
):
    cfg = CONFIG[
        index_name
    ]

    print()
    print("=" * 110)

    print(
        "ALL-IN-ONE MARKET BEHAVIOR RESEARCH:",
        index_name,
    )

    print("=" * 110)

    rows = fetch_large_history(
        api,
        cfg["segment"],
        cfg["token"],
        INTERVAL,
        CHUNK_DAYS,
        MAX_CANDLES,
    )

    candles = normalize_rows(
        rows
    )

    days = group_by_day(
        candles
    )

    dates = list(
        days.keys()
    )

    print(
        "RAW ROWS:",
        len(rows),
    )

    print(
        "VALID CANDLES:",
        len(candles),
    )

    print(
        "TRADING DAYS:",
        len(dates),
    )

    if len(dates) < 2:
        print(
            "NOT ENOUGH DATA"
        )
        return

    all_signals = []

    stats = defaultdict(
        lambda: {
            "signals": 0,
            "days": set(),
            "times": [],
            "mfe": [],
            "mae": [],
        }
    )

    outcome_stats = defaultdict(
        lambda: {
            "T": 0,
            "S": 0,
            "NONE": 0,
        }
    )

    for d in range(
        1,
        len(dates),
    ):

        prev_date = dates[
            d - 1
        ]

        current_date = dates[d]

        prev_day = days[
            prev_date
        ]

        current_day = days[
            current_date
        ]

        prev = previous_day_context(
            prev_day
        )

        signals = generate_day_signals(
            current_day,
            prev,
        )

        for signal in signals:

            signal["date"] = (
                current_date
            )

            all_signals.append(
                signal
            )

            rule = signal[
                "rule"
            ]

            stats[
                rule
            ]["signals"] += 1

            stats[
                rule
            ]["days"].add(
                current_date
            )

            stats[
                rule
            ]["times"].append(
                signal["time"]
            )

            mfe, mae = (
                move_capture_stats(
                    current_day,
                    signal,
                )
            )

            stats[
                rule
            ]["mfe"].append(
                mfe
            )

            stats[
                rule
            ]["mae"].append(
                mae
            )

            for (
                target_pct,
                stop_pct,
            ) in TARGET_SL_MATRIX:

                for window in (
                    FORWARD_WINDOWS
                ):

                    outcome = (
                        target_before_stop(
                            current_day,
                            signal[
                                "index"
                            ],
                            signal[
                                "direction"
                            ],
                            target_pct,
                            stop_pct,
                            window,
                        )
                    )

                    key = (
                        rule,
                        target_pct,
                        stop_pct,
                        window,
                    )

                    outcome_stats[
                        key
                    ][outcome] += 1

    total_test_days = (
        len(dates) - 1
    )

    print()
    print("=" * 110)

    print(
        "PHASE-1 RULE FREQUENCY"
    )

    print("=" * 110)

    ranked_rules = []

    for rule, bucket in (
        stats.items()
    ):

        signals = bucket[
            "signals"
        ]

        active_days = len(
            bucket["days"]
        )

        signals_per_day = (
            signals
            / total_test_days
            if total_test_days
            else 0
        )

        no_signal_days = (
            total_test_days
            - active_days
        )

        avg_mfe = (
            sum(
                bucket["mfe"]
            )
            / len(
                bucket["mfe"]
            )
            if bucket["mfe"]
            else 0
        )

        avg_mae = (
            sum(
                bucket["mae"]
            )
            / len(
                bucket["mae"]
            )
            if bucket["mae"]
            else 0
        )

        avg_minutes = 0

        if bucket["times"]:

            minute_values = []

            for t in bucket[
                "times"
            ]:

                minute_values.append(
                    (
                        t.hour * 60
                        + t.minute
                    )
                    - (
                        9 * 60
                        + 15
                    )
                )

            avg_minutes = (
                sum(
                    minute_values
                )
                / len(
                    minute_values
                )
            )

        ranked_rules.append(
            (
                signals_per_day,
                signals,
                rule,
                active_days,
                no_signal_days,
                avg_mfe,
                avg_mae,
                avg_minutes,
            )
        )

    ranked_rules.sort(
        reverse=True
    )

    for (
        signals_per_day,
        signals,
        rule,
        active_days,
        no_signal_days,
        avg_mfe,
        avg_mae,
        avg_minutes,
    ) in ranked_rules:

        print(
            f"{rule:30s} | "
            f"SIGNALS {signals:4d} | "
            f"SIG/DAY {signals_per_day:.2f} | "
            f"ACTIVE DAYS {active_days:3d} | "
            f"NO-SIGNAL {no_signal_days:3d} | "
            f"AVG ENTRY +{avg_minutes:.0f} MIN | "
            f"MFE {avg_mfe:.3f}% | "
            f"MAE {avg_mae:.3f}%"
        )

    print()
    print("=" * 110)

    print(
        "PHASE-2 ALL TARGET / SL / WINDOW TESTS"
    )

    print("=" * 110)

    ranking = []

    for key, result in (
        outcome_stats.items()
    ):

        (
            rule,
            target_pct,
            stop_pct,
            window,
        ) = key

        t = result["T"]
        s = result["S"]
        none = result["NONE"]

        signals = (
            t
            + s
            + none
        )

        resolved = (
            t + s
        )

        win_rate = (
            t
            / resolved
            * 100
            if resolved
            else 0
        )

        coverage = (
            resolved
            / signals
            * 100
            if signals
            else 0
        )

        sig_per_day = (
            signals
            / total_test_days
            if total_test_days
            else 0
        )

        # Practical score:
        # win rate + resolution + frequency.
        # Frequency capped so extremely noisy
        # rules cannot dominate.
        frequency_score = min(
            sig_per_day,
            2.0,
        ) * 10

        practical_score = (
            win_rate
            * 0.55
            + coverage
            * 0.30
            + frequency_score
        )

        ranking.append(
            (
                practical_score,
                rule,
                target_pct,
                stop_pct,
                window,
                signals,
                sig_per_day,
                t,
                s,
                none,
                win_rate,
                coverage,
            )
        )

    ranking.sort(
        reverse=True
    )

    for rank, item in enumerate(
        ranking[:50],
        1,
    ):

        (
            score,
            rule,
            target_pct,
            stop_pct,
            window,
            signals,
            sig_per_day,
            t,
            s,
            none,
            win_rate,
            coverage,
        ) = item

        print(
            f"#{rank:02d} | "
            f"{rule:28s} | "
            f"TGT {target_pct:.2f}% | "
            f"SL {stop_pct:.2f}% | "
            f"{window:2d}C | "
            f"SIG {signals:3d} | "
            f"{sig_per_day:.2f}/DAY | "
            f"T {t:3d} | "
            f"S {s:3d} | "
            f"N {none:3d} | "
            f"WIN {win_rate:6.2f}% | "
            f"RES {coverage:6.2f}% | "
            f"SCORE {score:6.2f}"
        )

    print()
    print("=" * 110)

    print(
        "PHASE-3 DAILY COMBINED OPPORTUNITY COUNT"
    )

    print("=" * 110)

    daily_counts = defaultdict(
        int
    )

    for signal in all_signals:
        daily_counts[
            signal["date"]
        ] += 1

    counts = []

    for date in dates[1:]:

        count = daily_counts.get(
            date,
            0,
        )

        counts.append(
            count
        )

    avg_daily = (
        sum(counts)
        / len(counts)
        if counts
        else 0
    )

    zero_days = sum(
        1
        for x in counts
        if x == 0
    )

    days_1_2 = sum(
        1
        for x in counts
        if 1 <= x <= 2
    )

    days_3_5 = sum(
        1
        for x in counts
        if 3 <= x <= 5
    )

    days_6_plus = sum(
        1
        for x in counts
        if x >= 6
    )

    print(
        "TOTAL UNIQUE RULE EVENTS:",
        len(all_signals),
    )

    print(
        "AVG RAW OPPORTUNITIES/DAY:",
        f"{avg_daily:.2f}",
    )

    print(
        "ZERO EVENT DAYS:",
        zero_days,
        "/",
        total_test_days,
    )

    print(
        "1-2 EVENT DAYS:",
        days_1_2,
    )

    print(
        "3-5 EVENT DAYS:",
        days_3_5,
    )

    print(
        "6+ EVENT DAYS:",
        days_6_plus,
    )

    print()
    print(
        "NOTE: Combined events can overlap."
    )

    print(
        "Next phase should merge overlapping rules "
        "into one actual trade opportunity."
    )


def main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    api = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    for index_name in (
        "NIFTY",
        "SENSEX",
    ):

        try:

            research_index(
                api,
                index_name,
            )

        except Exception as e:

            print(
                "\nERROR",
                index_name,
                type(e).__name__,
                e,
            )


if __name__ == "__main__":
    main()
