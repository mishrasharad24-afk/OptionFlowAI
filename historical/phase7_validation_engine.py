from collections import defaultdict, Counter

from historical.phase4_cluster_engine import merge_signal_clusters
from historical.phase6_quality_engine import _tier, _time_bucket


def _pct(n, d):
    return (100.0 * n / d) if d else 0.0


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


def _print_row(name, stats, total_days=None):
    resolved = stats["T"] + stats["S"]
    win = _pct(stats["T"], resolved)
    res = _pct(resolved, stats["SIG"])

    if total_days:
        per_day = stats["SIG"] / total_days
        day_text = f" | {per_day:5.2f}/DAY"
    else:
        day_text = ""

    print(
        f"{name:<55}"
        f" | SIG {stats['SIG']:4d}"
        f"{day_text}"
        f" | T {stats['T']:4d}"
        f" | S {stats['S']:4d}"
        f" | N {stats['NONE']:4d}"
        f" | WIN {win:6.2f}%"
        f" | RES {res:6.2f}%"
    )


def run_phase7(
    all_signals,
    days,
    dates,
    target_before_stop,
):
    print()
    print("=" * 110)
    print("PHASE-7 A+ VALIDATION / STABILITY / EXPECTANCY / WALK-FORWARD")
    print("=" * 110)

    cluster_gap = 2

    clusters = merge_signal_clusters(
        all_signals,
        cluster_gap=cluster_gap,
    )

    aplus = [
        cluster
        for cluster in clusters
        if _tier(cluster) == "A+"
        and cluster["date"] in days
    ]

    print("PRIMARY CLUSTER GAP:", cluster_gap, "CANDLES")
    print("TOTAL CLUSTERS:", len(clusters))
    print("A+ CLUSTERS:", len(aplus))
    print("TEST DAYS:", len(dates))

    targets = [0.10, 0.15, 0.20, 0.30]
    stop_pct = 0.10
    window = 15

    # ==================================================
    # 1. OVERALL A+ EXPECTANCY
    # ==================================================

    print()
    print("-" * 110)
    print("A+ OVERALL EXPECTANCY | SL 0.10% | WINDOW 15C")
    print("-" * 110)

    for target in targets:
        stats = _new_stats()

        for cluster in aplus:
            result = _outcome(
                days[cluster["date"]],
                cluster,
                target_before_stop,
                target,
                stop_pct,
                window,
            )
            _add_result(stats, result)

        resolved = stats["T"] + stats["S"]
        win_rate = _pct(stats["T"], resolved) / 100.0

        # Expectancy in units of underlying percentage move.
        expectancy = (
            win_rate * target
            - (1.0 - win_rate) * stop_pct
        )

        _print_row(
            f"TARGET {target:.2f}% | EXP {expectancy:+.4f}%",
            stats,
            len(dates),
        )

    # ==================================================
    # 2. DAY-BY-DAY A+ STABILITY
    # ==================================================

    print()
    print("-" * 110)
    print("A+ DAY-BY-DAY STABILITY | TARGET 0.20%")
    print("-" * 110)

    daily_stats = defaultdict(_new_stats)

    for cluster in aplus:
        date = cluster["date"]

        result = _outcome(
            days[date],
            cluster,
            target_before_stop,
            0.20,
            stop_pct,
            window,
        )

        _add_result(
            daily_stats[date],
            result,
        )

    profitable_days = 0
    losing_days = 0
    flat_days = 0
    active_days = 0

    for date in sorted(daily_stats):
        stats = daily_stats[date]

        if stats["SIG"] == 0:
            continue

        active_days += 1

        # 2R target versus 1R stop.
        pnl_r = (
            stats["T"] * 2.0
            - stats["S"]
        )

        if pnl_r > 0:
            profitable_days += 1
        elif pnl_r < 0:
            losing_days += 1
        else:
            flat_days += 1

        print(
            f"{str(date):<15}"
            f" | SIG {stats['SIG']:3d}"
            f" | T {stats['T']:3d}"
            f" | S {stats['S']:3d}"
            f" | N {stats['NONE']:3d}"
            f" | NET {pnl_r:+6.2f}R"
        )

    print()
    print(
        "ACTIVE DAYS:",
        active_days,
        "| PROFITABLE:",
        profitable_days,
        "| LOSING:",
        losing_days,
        "| FLAT:",
        flat_days,
    )

    print(
        "PROFITABLE ACTIVE DAYS:",
        f"{_pct(profitable_days, active_days):.2f}%",
    )

    # ==================================================
    # 3. A+ DIRECTION STABILITY
    # ==================================================

    print()
    print("-" * 110)
    print("A+ DIRECTION VALIDATION | TARGET 0.20%")
    print("-" * 110)

    direction_stats = defaultdict(_new_stats)

    for cluster in aplus:
        result = _outcome(
            days[cluster["date"]],
            cluster,
            target_before_stop,
            0.20,
            stop_pct,
            window,
        )

        _add_result(
            direction_stats[cluster["direction"]],
            result,
        )

    for name, stats in sorted(
        direction_stats.items(),
        key=lambda x: x[1]["T"],
        reverse=True,
    ):
        _print_row(name, stats, len(dates))

    # ==================================================
    # 4. A+ TIME-BUCKET VALIDATION
    # ==================================================

    print()
    print("-" * 110)
    print("A+ TIME VALIDATION | TARGET 0.20%")
    print("-" * 110)

    time_stats = defaultdict(_new_stats)

    for cluster in aplus:
        bucket = _time_bucket(
            cluster["time"]
        )

        result = _outcome(
            days[cluster["date"]],
            cluster,
            target_before_stop,
            0.20,
            stop_pct,
            window,
        )

        _add_result(
            time_stats[bucket],
            result,
        )

    for name, stats in sorted(
        time_stats.items(),
        key=lambda x: x[1]["SIG"],
        reverse=True,
    ):
        _print_row(name, stats, len(dates))

    # ==================================================
    # 5. A+ RULE PRESENCE
    # ==================================================

    print()
    print("-" * 110)
    print("A+ RULE PRESENCE IN 0.20% TARGET WINS")
    print("-" * 110)

    win_rule_counter = Counter()
    loss_rule_counter = Counter()

    for cluster in aplus:
        result = _outcome(
            days[cluster["date"]],
            cluster,
            target_before_stop,
            0.20,
            stop_pct,
            window,
        )

        for rule in set(
            cluster.get("rules", [])
        ):
            if result == "T":
                win_rule_counter[rule] += 1
            elif result == "S":
                loss_rule_counter[rule] += 1

    all_rules = (
        set(win_rule_counter)
        | set(loss_rule_counter)
    )

    rows = []

    for rule in all_rules:
        wins = win_rule_counter[rule]
        losses = loss_rule_counter[rule]
        resolved = wins + losses

        if resolved == 0:
            continue

        rows.append(
            (
                _pct(wins, resolved),
                resolved,
                wins,
                losses,
                rule,
            )
        )

    rows.sort(reverse=True)

    for i, row in enumerate(
        rows[:30],
        1,
    ):
        win, resolved, wins, losses, rule = row

        print(
            f"#{i:02d} | {rule:<40}"
            f" | RES {resolved:3d}"
            f" | T {wins:3d}"
            f" | S {losses:3d}"
            f" | WIN {win:6.2f}%"
        )

    # ==================================================
    # 6. CHRONOLOGICAL WALK-FORWARD
    # ==================================================

    print()
    print("-" * 110)
    print("A+ CHRONOLOGICAL WALK-FORWARD | TARGET 0.20%")
    print("-" * 110)

    ordered_dates = sorted(dates)

    if len(ordered_dates) >= 2:
        split = int(
            len(ordered_dates) * 0.70
        )

        split = max(
            1,
            min(
                split,
                len(ordered_dates) - 1,
            ),
        )

        train_dates = set(
            ordered_dates[:split]
        )

        test_dates = set(
            ordered_dates[split:]
        )

        train_stats = _new_stats()
        test_stats = _new_stats()

        for cluster in aplus:
            date = cluster["date"]

            result = _outcome(
                days[date],
                cluster,
                target_before_stop,
                0.20,
                stop_pct,
                window,
            )

            if date in train_dates:
                _add_result(
                    train_stats,
                    result,
                )
            elif date in test_dates:
                _add_result(
                    test_stats,
                    result,
                )

        print(
            "TRAIN:",
            ordered_dates[0],
            "TO",
            ordered_dates[split - 1],
        )

        _print_row(
            "TRAIN 70%",
            train_stats,
            len(train_dates),
        )

        print(
            "TEST:",
            ordered_dates[split],
            "TO",
            ordered_dates[-1],
        )

        _print_row(
            "OUT-OF-SAMPLE 30%",
            test_stats,
            len(test_dates),
        )

    # ==================================================
    # 7. SIGNAL CONCENTRATION
    # ==================================================

    print()
    print("-" * 110)
    print("A+ SIGNAL CONCENTRATION BY DAY")
    print("-" * 110)

    concentration = Counter(
        cluster["date"]
        for cluster in aplus
    )

    for date, count in concentration.most_common(15):
        print(
            f"{str(date):<15}"
            f" | A+ SIGNALS {count:3d}"
            f" | SHARE {_pct(count, len(aplus)):6.2f}%"
        )

    print()
    print("=" * 110)
    print("PHASE-7 COMPLETE")
    print("=" * 110)
