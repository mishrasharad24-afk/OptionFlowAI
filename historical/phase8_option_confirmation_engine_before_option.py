from collections import defaultdict

from historical.phase4_cluster_engine import merge_signal_clusters
from historical.phase6_quality_engine import _tier


def _candle_direction(candle):
    """
    Basic candle formation:
    +1 = bullish candle
    -1 = bearish candle
     0 = neutral/doji
    """
    o = float(candle["open"])
    c = float(candle["close"])

    if c > o:
        return 1

    if c < o:
        return -1

    return 0


def _formation_score(candles, index, direction):
    """
    Check recent 3-candle formation in the underlying.

    Returns score from 0 to 3.
    """
    if index < 2 or index >= len(candles):
        return 0

    recent = candles[index - 2:index + 1]

    if direction == "BULLISH":
        return sum(
            1
            for candle in recent
            if _candle_direction(candle) == 1
        )

    if direction == "BEARISH":
        return sum(
            1
            for candle in recent
            if _candle_direction(candle) == -1
        )

    return 0


def run_phase8(
    all_signals,
    days,
    dates,
    target_before_stop,
):
    """
    Phase-8:
    Formation confirmation research.

    First validates whether A+ spot signals also have
    same-direction candle formation around entry.

    This creates the framework for later CE/PE option
    candle formation confirmation.
    """

    print()
    print("=" * 110)
    print(
        "PHASE-8 A+ FORMATION CONFIRMATION RESEARCH"
    )
    print("=" * 110)

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
        "TOTAL A+ CLUSTERS:",
        len(aplus),
    )

    stats = defaultdict(
        lambda: {
            "SIG": 0,
            "T": 0,
            "S": 0,
            "NONE": 0,
        }
    )

    for cluster in aplus:

        date = cluster["date"]
        index = cluster["index"]
        direction = cluster["direction"]

        day = days[date]

        score = _formation_score(
            day,
            index,
            direction,
        )

        if score >= 3:
            formation = "STRONG_3_OF_3"

        elif score >= 2:
            formation = "CONFIRMED_2_OF_3"

        else:
            formation = "WEAK"

        result = target_before_stop(
            day,
            index,
            direction,
            0.20,
            0.10,
            15,
        )

        stats[formation]["SIG"] += 1

        if result == "T":
            stats[formation]["T"] += 1

        elif result == "S":
            stats[formation]["S"] += 1

        else:
            stats[formation]["NONE"] += 1

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

        s = stats[formation]

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
            f"{formation:<25}"
            f" | SIG {s['SIG']:4d}"
            f" | T {s['T']:4d}"
            f" | S {s['S']:4d}"
            f" | N {s['NONE']:4d}"
            f" | WIN {win:6.2f}%"
        )

    print()
    print(
        "NOTE: This phase validates spot candle formation first."
    )
    print(
        "Next layer will compare the same formation with CE/PE option candles."
    )
