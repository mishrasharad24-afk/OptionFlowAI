from collections import defaultdict, Counter
from historical.phase4_cluster_engine import merge_signal_clusters


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


def _pct(n, d):
    return (100.0 * n / d) if d else 0.0


def _time_bucket(time_value):
    """
    Convert datetime/time/string values into broad intraday buckets.
    Supports datetime objects and strings such as:
    09:15
    09:15:00
    2026-07-01 09:15:00
    2026-07-01T09:15:00
    """
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


def _print_rule_stats(
    title,
    stats,
    minimum=5,
    limit=25,
):
    print()
    print("-" * 110)
    print(title)
    print("-" * 110)

    rows = []

    for name, s in stats.items():

        total = s["T"] + s["S"] + s["NONE"]

        resolved = s["T"] + s["S"]

        if total < minimum:
            continue

        win = _pct(
            s["T"],
            resolved,
        )

        resolution = _pct(
            resolved,
            total,
        )

        rows.append(
            (
                win,
                s["T"],
                total,
                resolution,
                name,
                s,
            )
        )

    rows.sort(
        reverse=True,
        key=lambda x: (
            x[0],
            x[1],
            x[2],
        ),
    )

    if not rows:
        print("NO QUALIFYING DATA")
        return

    for rank, row in enumerate(
        rows[:limit],
        1,
    ):
        (
            win,
            wins,
            total,
            resolution,
            name,
            s,
        ) = row

        print(
            f"#{rank:02d} | "
            f"{str(name):45s} | "
            f"SIG {total:3d} | "
            f"T {s['T']:3d} | "
            f"S {s['S']:3d} | "
            f"N {s['NONE']:3d} | "
            f"WIN {win:6.2f}% | "
            f"RES {resolution:6.2f}%"
        )


def run_phase5(
    all_signals,
    days,
    dates,
    target_before_stop,
):
    print()
    print("=" * 110)
    print(
        "PHASE-5 FORMATION / CONDITION / BIG-MOVE RESEARCH"
    )
    print("=" * 110)

    # Phase-4 showed that nearby signals are much more
    # meaningful when merged. Use 2 candles (~10 min)
    # as the primary formation research cluster.
    cluster_gap = 2

    clusters = merge_signal_clusters(
        all_signals,
        cluster_gap=cluster_gap,
    )

    print(
        "PRIMARY CLUSTER GAP:",
        cluster_gap,
        "CANDLES",
    )

    print(
        "TOTAL FORMATION CLUSTERS:",
        len(clusters),
    )

    print(
        "TEST TARGETS:",
        "0.10%, 0.15%, 0.20%, 0.30%",
    )

    print(
        "STOP:",
        "0.10%",
        "| WINDOW:",
        "15 CANDLES",
    )

    targets = [
        0.10,
        0.15,
        0.20,
        0.30,
    ]

    # --------------------------------------------------
    # Overall consensus performance
    # --------------------------------------------------

    consensus_stats = {
        target: defaultdict(
            lambda: {
                "T": 0,
                "S": 0,
                "NONE": 0,
            }
        )
        for target in targets
    }

    # --------------------------------------------------
    # Rule-level performance
    # --------------------------------------------------

    rule_stats = {
        target: defaultdict(
            lambda: {
                "T": 0,
                "S": 0,
                "NONE": 0,
            }
        )
        for target in targets
    }

    # --------------------------------------------------
    # Exact formation combinations
    # --------------------------------------------------

    combo_stats = {
        target: defaultdict(
            lambda: {
                "T": 0,
                "S": 0,
                "NONE": 0,
            }
        )
        for target in targets
    }

    # --------------------------------------------------
    # Direction performance
    # --------------------------------------------------

    direction_stats = {
        target: defaultdict(
            lambda: {
                "T": 0,
                "S": 0,
                "NONE": 0,
            }
        )
        for target in targets
    }

    # --------------------------------------------------
    # Time bucket performance
    # --------------------------------------------------

    time_stats = {
        target: defaultdict(
            lambda: {
                "T": 0,
                "S": 0,
                "NONE": 0,
            }
        )
        for target in targets
    }

    # --------------------------------------------------
    # Rule + direction
    # --------------------------------------------------

    rule_direction_stats = {
        target: defaultdict(
            lambda: {
                "T": 0,
                "S": 0,
                "NONE": 0,
            }
        )
        for target in targets
    }

    winning_rule_counter = Counter()
    big_move_rule_counter = Counter()
    big_move_combo_counter = Counter()

    for cluster in clusters:

        date = cluster["date"]

        if date not in days:
            continue

        day = days[date]

        rules = tuple(
            sorted(
                set(
                    cluster["rules"]
                )
            )
        )

        combo_name = " + ".join(
            rules
        )

        consensus = cluster[
            "consensus"
        ]

        if consensus >= 4:
            consensus_group = "CONS>=4"

        elif consensus == 3:
            consensus_group = "CONS=3"

        elif consensus == 2:
            consensus_group = "CONS=2"

        else:
            consensus_group = "CONS=1"

        direction = cluster[
            "direction"
        ]

        bucket = _time_bucket(
            cluster["time"]
        )

        for target in targets:

            result = _outcome(
                day,
                cluster,
                target_before_stop,
                target_pct=target,
                stop_pct=0.10,
                window=15,
            )

            consensus_stats[
                target
            ][
                consensus_group
            ][result] += 1

            direction_stats[
                target
            ][
                direction
            ][result] += 1

            time_stats[
                target
            ][
                bucket
            ][result] += 1

            combo_stats[
                target
            ][
                combo_name
            ][result] += 1

            for rule in rules:

                rule_stats[
                    target
                ][
                    rule
                ][result] += 1

                key = (
                    direction
                    + " | "
                    + rule
                )

                rule_direction_stats[
                    target
                ][
                    key
                ][result] += 1

            # Count formations involved in successful
            # standard moves.
            if (
                target == 0.10
                and result == "T"
            ):
                for rule in rules:
                    winning_rule_counter[
                        rule
                    ] += 1

            # 0.20% is treated as meaningful big move.
            if (
                target == 0.20
                and result == "T"
            ):
                for rule in rules:
                    big_move_rule_counter[
                        rule
                    ] += 1

                big_move_combo_counter[
                    combo_name
                ] += 1

    # ==================================================
    # SECTION 1
    # CONSENSUS IMPACT
    # ==================================================

    for target in targets:

        _print_rule_stats(
            (
                f"CONSENSUS IMPACT | "
                f"TARGET {target:.2f}% | "
                f"SL 0.10% | 15C"
            ),
            consensus_stats[target],
            minimum=1,
            limit=20,
        )

    # ==================================================
    # SECTION 2
    # BEST INDIVIDUAL FORMATIONS
    # ==================================================

    for target in targets:

        _print_rule_stats(
            (
                f"BEST INDIVIDUAL RULES / FORMATIONS | "
                f"TARGET {target:.2f}%"
            ),
            rule_stats[target],
            minimum=10,
            limit=30,
        )

    # ==================================================
    # SECTION 3
    # BEST EXACT RULE COMBINATIONS
    # ==================================================

    for target in (
        0.10,
        0.15,
        0.20,
    ):

        _print_rule_stats(
            (
                f"BEST EXACT FORMATION COMBINATIONS | "
                f"TARGET {target:.2f}%"
            ),
            combo_stats[target],
            minimum=5,
            limit=30,
        )

    # ==================================================
    # SECTION 4
    # BULLISH VS BEARISH
    # ==================================================

    for target in targets:

        _print_rule_stats(
            (
                f"DIRECTION PERFORMANCE | "
                f"TARGET {target:.2f}%"
            ),
            direction_stats[target],
            minimum=1,
            limit=10,
        )

    # ==================================================
    # SECTION 5
    # TIME OF DAY
    # ==================================================

    for target in (
        0.10,
        0.15,
        0.20,
    ):

        _print_rule_stats(
            (
                f"TIME-OF-DAY PERFORMANCE | "
                f"TARGET {target:.2f}%"
            ),
            time_stats[target],
            minimum=5,
            limit=10,
        )

    # ==================================================
    # SECTION 6
    # RULE + DIRECTION
    # ==================================================

    for target in (
        0.10,
        0.15,
        0.20,
    ):

        _print_rule_stats(
            (
                f"RULE + DIRECTION PERFORMANCE | "
                f"TARGET {target:.2f}%"
            ),
            rule_direction_stats[target],
            minimum=10,
            limit=30,
        )

    # ==================================================
    # SECTION 7
    # FORMATIONS MOST PRESENT IN WINNERS
    # ==================================================

    print()
    print("=" * 110)
    print(
        "FORMATIONS MOST PRESENT IN 0.10% WINNING MOVES"
    )
    print("=" * 110)

    for rank, (
        rule,
        count,
    ) in enumerate(
        winning_rule_counter.most_common(
            30
        ),
        1,
    ):
        print(
            f"#{rank:02d} | "
            f"{rule:40s} | "
            f"WINNING MOVE PRESENCE {count:4d}"
        )

    # ==================================================
    # SECTION 8
    # BIG MOVE FORMATION IMPORTANCE
    # ==================================================

    print()
    print("=" * 110)
    print(
        "FORMATIONS MOST PRESENT IN 0.20% BIG MOVES"
    )
    print("=" * 110)

    for rank, (
        rule,
        count,
    ) in enumerate(
        big_move_rule_counter.most_common(
            30
        ),
        1,
    ):
        print(
            f"#{rank:02d} | "
            f"{rule:40s} | "
            f"BIG-MOVE PRESENCE {count:4d}"
        )

    print()
    print("=" * 110)
    print(
        "EXACT FORMATION COMBINATIONS MOST PRESENT IN 0.20% BIG MOVES"
    )
    print("=" * 110)

    for rank, (
        combo,
        count,
    ) in enumerate(
        big_move_combo_counter.most_common(
            30
        ),
        1,
    ):
        print(
            f"#{rank:02d} | "
            f"{combo} | "
            f"BIG-MOVE WINS {count}"
        )

    # ==================================================
    # SECTION 9
    # WIN-RATE LIFT ANALYSIS
    # Compare each rule with overall cluster baseline
    # ==================================================

    print()
    print("=" * 110)
    print(
        "WIN-RATE LIFT: WHICH CONDITION IMPROVES THE BASELINE?"
    )
    print("=" * 110)

    for target in (
        0.10,
        0.15,
        0.20,
    ):

        all_t = 0
        all_s = 0

        for s in direction_stats[
            target
        ].values():

            all_t += s["T"]
            all_s += s["S"]

        baseline = _pct(
            all_t,
            all_t + all_s,
        )

        lifts = []

        for rule, s in rule_stats[
            target
        ].items():

            resolved = (
                s["T"]
                + s["S"]
            )

            total = (
                resolved
                + s["NONE"]
            )

            if total < 10:
                continue

            win = _pct(
                s["T"],
                resolved,
            )

            lift = (
                win
                - baseline
            )

            lifts.append(
                (
                    lift,
                    win,
                    total,
                    rule,
                )
            )

        lifts.sort(
            reverse=True,
            key=lambda x: (
                x[0],
                x[1],
                x[2],
            ),
        )

        print()
        print(
            f"TARGET {target:.2f}% "
            f"| BASELINE WIN RATE "
            f"{baseline:.2f}%"
        )

        for rank, (
            lift,
            win,
            total,
            rule,
        ) in enumerate(
            lifts[:20],
            1,
        ):

            print(
                f"#{rank:02d} | "
                f"{rule:40s} | "
                f"SIG {total:3d} | "
                f"WIN {win:6.2f}% | "
                f"LIFT {lift:+6.2f} PP"
            )

    print()
    print("=" * 110)
    print(
        "PHASE-5 COMPLETE"
    )
    print("=" * 110)
