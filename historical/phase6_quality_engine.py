from collections import defaultdict
from historical.phase4_cluster_engine import merge_signal_clusters


def _pct(n, d):
    return (100.0 * n / d) if d else 0.0


def _time_bucket(time_value):
    try:
        if hasattr(time_value, "hour"):
            hour = int(time_value.hour)
            minute = int(time_value.minute)
        else:
            text = str(time_value).strip()

            if "T" in text:
                text = text.split("T")[-1]
            elif " " in text:
                text = text.split()[-1]

            parts = text.split(":")
            hour = int(parts[0])
            minute = int(parts[1])

        mins = hour * 60 + minute

    except Exception:
        return "UNKNOWN"

    if mins < 10 * 60:
        return "OPEN_0915_1000"
    if mins < 11 * 60:
        return "MORNING_1000_1100"
    if mins < 13 * 60:
        return "MIDDAY_1100_1300"
    if mins < 14 * 60 + 30:
        return "AFTERNOON_1300_1430"

    return "LATE_1430_CLOSE"


def _outcome(
    day,
    cluster,
    target_before_stop,
    target_pct,
    stop_pct=0.10,
    window=15,
):
    return target_before_stop(
        day,
        cluster["index"],
        cluster["direction"],
        target_pct,
        stop_pct,
        window,
    )


def _stats_for_clusters(
    clusters,
    days,
    target_before_stop,
    target_pct,
):
    stats = {
        "SIG": 0,
        "T": 0,
        "S": 0,
        "NONE": 0,
    }

    for cluster in clusters:
        day = days.get(cluster["date"])
        if day is None:
            continue

        result = _outcome(
            day,
            cluster,
            target_before_stop,
            target_pct,
        )

        stats["SIG"] += 1

        if result == "T":
            stats["T"] += 1
        elif result == "S":
            stats["S"] += 1
        else:
            stats["NONE"] += 1

    resolved = stats["T"] + stats["S"]
    stats["WIN"] = _pct(stats["T"], resolved)
    stats["RES"] = _pct(resolved, stats["SIG"])

    return stats


def _tier(cluster):
    rules = set(cluster.get("rules", []))
    direction = cluster["direction"]
    consensus = cluster.get("consensus", len(rules))

    bullish_core = {
        "DISP_30M",
        "VELOCITY_2C",
        "VELOCITY_3C",
        "OR5_BREAKOUT",
        "OR15_BREAKOUT",
        "OR30_BREAKOUT",
        "PDH_BREAKOUT",
        "ABOVE_PDH_EXPANSION",
        "GAP_UP_CONTINUATION",
    }

    bearish_core = {
        "DISP_30M",
        "VELOCITY_2C",
        "VELOCITY_3C",
        "OR5_BREAKDOWN",
        "OR15_BREAKDOWN",
        "OR30_BREAKDOWN",
        "GAP_DOWN_CONTINUATION",
    }

    if direction == "BULLISH":
        core_hits = len(rules & bullish_core)

        if consensus >= 4 and core_hits >= 2:
            return "A+"

        if consensus >= 3 and core_hits >= 1:
            return "A"

        if consensus >= 2 and core_hits >= 1:
            return "B"

        return "SKIP"

    core_hits = len(rules & bearish_core)

    if consensus >= 4 and core_hits >= 3:
        return "A+"

    if consensus >= 4 and core_hits >= 2:
        return "A"

    if consensus >= 3 and core_hits >= 1:
        return "B"

    return "SKIP"


def _print_stats(title, rows, total_days):
    print()
    print("-" * 110)
    print(title)
    print("-" * 110)

    for name, stats in rows:
        sig = stats["SIG"]
        per_day = sig / total_days if total_days else 0.0

        print(
            f"{name:45s} | "
            f"SIG {sig:4d} | "
            f"{per_day:5.2f}/DAY | "
            f"T {stats['T']:4d} | "
            f"S {stats['S']:4d} | "
            f"N {stats['NONE']:4d} | "
            f"WIN {stats['WIN']:6.2f}% | "
            f"RES {stats['RES']:6.2f}%"
        )


def run_phase6(
    all_signals,
    days,
    dates,
    target_before_stop,
):
    print()
    print("=" * 110)
    print("PHASE-6 QUALITY TIER / TIME / DIRECTION / BIG-MOVE RESEARCH")
    print("=" * 110)

    cluster_gap = 2

    clusters = merge_signal_clusters(
        all_signals,
        cluster_gap=cluster_gap,
    )

    total_days = max(1, len(dates) - 1)

    print("PRIMARY CLUSTER GAP:", cluster_gap, "CANDLES")
    print("TOTAL CLUSTERS:", len(clusters))
    print("TEST DAYS:", total_days)

    tier_groups = defaultdict(list)
    time_groups = defaultdict(list)
    direction_groups = defaultdict(list)
    tier_time_groups = defaultdict(list)
    tier_direction_groups = defaultdict(list)

    for cluster in clusters:
        tier = _tier(cluster)
        bucket = _time_bucket(cluster["time"])
        direction = cluster["direction"]

        cluster["phase6_tier"] = tier
        cluster["phase6_time_bucket"] = bucket

        tier_groups[tier].append(cluster)
        time_groups[bucket].append(cluster)
        direction_groups[direction].append(cluster)

        tier_time_groups[
            (tier, bucket)
        ].append(cluster)

        tier_direction_groups[
            (tier, direction)
        ].append(cluster)

    targets = [
        0.10,
        0.15,
        0.20,
        0.30,
    ]

    for target in targets:
        rows = []

        for tier in (
            "A+",
            "A",
            "B",
            "SKIP",
        ):
            stats = _stats_for_clusters(
                tier_groups[tier],
                days,
                target_before_stop,
                target,
            )

            rows.append(
                (tier, stats)
            )

        _print_stats(
            f"QUALITY TIERS | TARGET {target:.2f}% | SL 0.10% | 15C",
            rows,
            total_days,
        )

    for target in (
        0.10,
        0.20,
    ):
        rows = []

        for bucket in sorted(time_groups):
            stats = _stats_for_clusters(
                time_groups[bucket],
                days,
                target_before_stop,
                target,
            )

            rows.append(
                (bucket, stats)
            )

        _print_stats(
            f"TIME-OF-DAY | TARGET {target:.2f}%",
            rows,
            total_days,
        )

    for target in (
        0.10,
        0.20,
    ):
        rows = []

        for direction in (
            "BULLISH",
            "BEARISH",
        ):
            stats = _stats_for_clusters(
                direction_groups[direction],
                days,
                target_before_stop,
                target,
            )

            rows.append(
                (direction, stats)
            )

        _print_stats(
            f"DIRECTION | TARGET {target:.2f}%",
            rows,
            total_days,
        )

    for target in (
        0.10,
        0.20,
    ):
        rows = []

        for key, group in tier_direction_groups.items():
            tier, direction = key

            stats = _stats_for_clusters(
                group,
                days,
                target_before_stop,
                target,
            )

            rows.append(
                (
                    f"{tier} | {direction}",
                    stats,
                )
            )

        rows.sort(
            key=lambda x: (
                x[1]["WIN"],
                x[1]["SIG"],
            ),
            reverse=True,
        )

        _print_stats(
            f"TIER + DIRECTION | TARGET {target:.2f}%",
            rows,
            total_days,
        )

    for target in (
        0.10,
        0.20,
    ):
        rows = []

        for key, group in tier_time_groups.items():
            tier, bucket = key

            stats = _stats_for_clusters(
                group,
                days,
                target_before_stop,
                target,
            )

            rows.append(
                (
                    f"{tier} | {bucket}",
                    stats,
                )
            )

        rows.sort(
            key=lambda x: (
                x[1]["WIN"],
                x[1]["SIG"],
            ),
            reverse=True,
        )

        _print_stats(
            f"TIER + TIME | TARGET {target:.2f}%",
            rows,
            total_days,
        )

    print()
    print("=" * 110)
    print("PHASE-6 COMPLETE")
    print("=" * 110)
