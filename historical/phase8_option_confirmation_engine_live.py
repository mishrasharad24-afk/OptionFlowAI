from collections import defaultdict
from datetime import datetime, timedelta

from historical.phase4_cluster_engine import merge_signal_clusters
from historical.phase6_quality_engine import _tier
from historical.backtest_30day_chunk_base import (
    load_contracts,
    find_contract,
)


OPTION_CONFIG = {
    "NIFTY": {
        "opt_seg": "NFO",
        "gap": 50,
    },
    "SENSEX": {
        "opt_seg": "BFO",
        "gap": 100,
    },
}


def _candle_direction(candle):
    """
    Supports both:
    spot candle dict:
        {"open": ..., "close": ...}

    option API candle list:
        [timestamp, open, high, low, close, volume, ...]
    """
    try:
        if isinstance(candle, dict):
            o = float(candle["open"])
            c = float(candle["close"])
        else:
            o = float(candle[1])
            c = float(candle[4])

        if c > o:
            return 1
        if c < o:
            return -1
    except Exception:
        pass

    return 0


def _formation_score(candles, index, direction):
    """
    Spot 3-candle formation score.
    Returns 0 to 3.
    """
    if index < 2 or index >= len(candles):
        return 0

    recent = candles[index - 2:index + 1]

    wanted = 1 if direction == "BULLISH" else -1

    return sum(
        1
        for candle in recent
        if _candle_direction(candle) == wanted
    )


def _get_candles(response):
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


def _fetch_option_day(
    api,
    segment,
    token,
    day,
):
    """
    Fetch a small date window around one trading day.
    Cache prevents repeated API calls for the same token/day.
    """
    d = datetime.strptime(
        str(day),
        "%Y-%m-%d",
    )

    from_date = (
        d - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    to_date = (
        d + timedelta(days=1)
    ).strftime("%Y-%m-%d")

    try:
        response = api.get_historical_chart(
            segment,
            str(token),
            "5minute",
            from_date,
            to_date,
        )
    except Exception:
        return []

    rows = _get_candles(response)

    return [
        row
        for row in rows
        if row
        and str(row[0]).startswith(str(day))
    ]


def _option_map(rows):
    """
    Map option candles by HH:MM.
    """
    out = {}

    for row in rows:
        try:
            timestamp = str(row[0])
            time_key = timestamp[11:16]
            out[time_key] = row
        except Exception:
            continue

    return out



def _option_3c_score(
    omap,
    times,
    current_index,
    wanted_direction,
):
    """
    Placeholder for Live Option Chain scoring.
    Historical option candles have been disabled.
    """
    return 0


def _new_stats():
    return {
        "SIG": 0,
        "T": 0,
        "S": 0,
        "NONE": 0,
    }


def _add_result(stats, result):
    stats["SIG"] += 1

    if result == "T":
        stats["T"] += 1
    elif result == "S":
        stats["S"] += 1
    else:
        stats["NONE"] += 1


def _print_stats(name, s):
    resolved = (
        s["T"]
        + s["S"]
    )

    win = (
        100.0
        * s["T"]
        / resolved
        if resolved
        else 0.0
    )

    print(
        f"{name:<32}"
        f" | SIG {s['SIG']:4d}"
        f" | T {s['T']:4d}"
        f" | S {s['S']:4d}"
        f" | N {s['NONE']:4d}"
        f" | WIN {win:6.2f}%"
    )


def run_phase8(
    api,
    index_name,
    all_signals,
    days,
    dates,
    target_before_stop,
):
    """
    Phase-8:
    A+ spot formation + ATM CE/PE option confirmation.

    Bullish A+:
        CE should show bullish formation.
        PE should show bearish formation.

    Bearish A+:
        PE should show bullish formation.
        CE should show bearish formation.

    Research buckets:
        SPOT_ONLY
        OPTION_ONLY
        SPOT_OPTION_CONFIRMED
        SPOT_OPTION_DIVERGENCE
        NO_OPTION_DATA
    """

    print()
    print("=" * 110)
    print(
        "PHASE-8 A+ SPOT + ATM CE/PE OPTION CONFIRMATION RESEARCH"
    )
    print("=" * 110)

    cfg = OPTION_CONFIG[index_name]

    clusters = merge_signal_clusters(
        all_signals,
        cluster_gap=2,
    )

    aplus = [
        cluster
        for cluster in clusters
        if _tier(cluster) == "A+"
        and cluster["date"] in days
    ]

    print(
        "INDEX:",
        index_name,
        "| TOTAL A+ CLUSTERS:",
        len(aplus),
    )

    contracts = load_contracts(
        index_name
    )

    print(
        "OPTION CONTRACTS LOADED:",
        len(contracts),
    )

    spot_stats = defaultdict(
        _new_stats
    )

    option_stats = defaultdict(
        _new_stats
    )

    combined_stats = defaultdict(
        _new_stats
    )

    cache = {}

    option_data_found = 0
    option_data_missing = 0

    for cluster in aplus:
        date = cluster["date"]
        index = cluster["index"]
        direction = cluster["direction"]

        day = days[date]

        if (
            index < 0
            or index >= len(day)
        ):
            continue

        signal_time = cluster["time"]
        spot = float(
            day[index]["close"]
        )

        # -----------------------------------------
        # SPOT FORMATION
        # -----------------------------------------
        spot_score = _formation_score(
            day,
            index,
            direction,
        )

        if spot_score >= 3:
            spot_formation = (
                "STRONG_3_OF_3"
            )
        elif spot_score >= 2:
            spot_formation = (
                "CONFIRMED_2_OF_3"
            )
        else:
            spot_formation = "WEAK"

        result = target_before_stop(
            day,
            index,
            direction,
            0.20,
            0.10,
            15,
        )

        _add_result(
            spot_stats[spot_formation],
            result,
        )

        # -----------------------------------------
        # ATM + NEAREST VALID EXPIRY
        # -----------------------------------------
        atm = int(
            round(
                spot
                / cfg["gap"]
            )
            * cfg["gap"]
        )

        try:
            day_date = datetime.strptime(
                str(date),
                "%Y-%m-%d",
            ).date()
        except Exception:
            option_data_missing += 1
            _add_result(
                combined_stats[
                    "NO_OPTION_DATA"
                ],
                result,
            )
            continue

        expiries = sorted({
            x["expiry"]
            for x in contracts
            if x["expiry"] >= day_date
        })

        if not expiries:
            option_data_missing += 1
            _add_result(
                combined_stats[
                    "NO_OPTION_DATA"
                ],
                result,
            )
            continue

        expiry = expiries[0]

        ce = find_contract(
            contracts,
            expiry,
            atm,
            "CE",
        )

        pe = find_contract(
            contracts,
            expiry,
            atm,
            "PE",
        )

        if not ce or not pe:
            option_data_missing += 1
            _add_result(
                combined_stats[
                    "NO_OPTION_DATA"
                ],
                result,
            )
            continue

        # -----------------------------------------
        # FETCH CE / PE DATA WITH CACHE
        # -----------------------------------------
        ce_key = (
            str(ce["token"]),
            str(date),
        )

        pe_key = (
            str(pe["token"]),
            str(date),
        )

        if ce_key not in cache:
            cache[ce_key] = (
                _fetch_option_day(
                    api,
                    cfg["opt_seg"],
                    ce["token"],
                    date,
                )
            )

        if pe_key not in cache:
            cache[pe_key] = (
                _fetch_option_day(
                    api,
                    cfg["opt_seg"],
                    pe["token"],
                    date,
                )
            )

        ce_rows = cache[ce_key]
        pe_rows = cache[pe_key]

        ce_map = _option_map(
            ce_rows
        )

        pe_map = _option_map(
            pe_rows
        )

        # Spot day times are used so option candles
        # align exactly with the signal candle.
        times = [
            candle["time"]
            for candle in day
        ]

        if (
            signal_time not in ce_map
            or signal_time not in pe_map
            or index < 2
        ):
            option_data_missing += 1

            _add_result(
                combined_stats[
                    "NO_OPTION_DATA"
                ],
                result,
            )

            continue

        option_data_found += 1

        # -----------------------------------------
        # OPTION FORMATION LOGIC
        # -----------------------------------------
        if direction == "BULLISH":
            # CE should rise, PE should weaken.
            ce_score = _option_3c_score(
                ce_map,
                times,
                index,
                +1,
            )

            pe_score = _option_3c_score(
                pe_map,
                times,
                index,
                -1,
            )

        else:
            # PE should rise, CE should weaken.
            pe_score = _option_3c_score(
                pe_map,
                times,
                index,
                +1,
            )

            ce_score = _option_3c_score(
                ce_map,
                times,
                index,
                -1,
            )

        total_option_score = (
            ce_score
            + pe_score
        )

        # Maximum combined option score = 6.
        if (
            ce_score >= 2
            and pe_score >= 2
            and total_option_score >= 5
        ):
            option_formation = (
                "OPTION_STRONG"
            )

        elif (
            ce_score >= 2
            and pe_score >= 2
        ):
            option_formation = (
                "OPTION_CONFIRMED"
            )

        else:
            option_formation = (
                "OPTION_WEAK"
            )

        _add_result(
            option_stats[
                option_formation
            ],
            result,
        )

        # -----------------------------------------
        # COMBINED SPOT + OPTION BUCKET
        # -----------------------------------------
        spot_confirmed = (
            spot_score >= 2
        )

        option_confirmed = (
            ce_score >= 2
            and pe_score >= 2
        )

        if (
            spot_confirmed
            and option_confirmed
        ):
            bucket = (
                "SPOT_OPTION_CONFIRMED"
            )

        elif (
            spot_confirmed
            and not option_confirmed
        ):
            bucket = (
                "SPOT_OPTION_DIVERGENCE"
            )

        elif (
            not spot_confirmed
            and option_confirmed
        ):
            bucket = (
                "OPTION_ONLY"
            )

        else:
            bucket = "SPOT_ONLY"

        _add_result(
            combined_stats[bucket],
            result,
        )

    # =====================================================
    # OUTPUT
    # =====================================================

    print()
    print("-" * 110)
    print(
        "A+ SPOT FORMATION | TARGET 0.20% | SL 0.10% | WINDOW 15C"
    )
    print("-" * 110)

    for formation in (
        "STRONG_3_OF_3",
        "CONFIRMED_2_OF_3",
        "WEAK",
    ):
        _print_stats(
            formation,
            spot_stats[formation],
        )

    print()
    print("-" * 110)
    print(
        "A+ ATM OPTION FORMATION | CE/PE 3-CANDLE CONFIRMATION"
    )
    print("-" * 110)

    for formation in (
        "OPTION_STRONG",
        "OPTION_CONFIRMED",
        "OPTION_WEAK",
    ):
        _print_stats(
            formation,
            option_stats[formation],
        )

    print()
    print("-" * 110)
    print(
        "A+ SPOT + OPTION CONFIRMATION | TARGET 0.20%"
    )
    print("-" * 110)

    for bucket in (
        "SPOT_OPTION_CONFIRMED",
        "SPOT_OPTION_DIVERGENCE",
        "OPTION_ONLY",
        "SPOT_ONLY",
        "NO_OPTION_DATA",
    ):
        _print_stats(
            bucket,
            combined_stats[bucket],
        )

    print()
    print(
        "OPTION DATA FOUND:",
        option_data_found,
        "| OPTION DATA MISSING:",
        option_data_missing,
    )

    print()
    print("=" * 110)
    print("PHASE-8 COMPLETE")
    print("=" * 110)
