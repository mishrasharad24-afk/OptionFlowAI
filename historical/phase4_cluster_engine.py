from collections import defaultdict


def merge_signal_clusters(all_signals, cluster_gap=2):
    """
    Merge signals from the same date and direction when they occur
    within cluster_gap candles of the current cluster.

    cluster_gap=2 on 5-minute candles means signals within roughly
    10 minutes are treated as one market opportunity.
    """

    grouped = defaultdict(list)

    for signal in all_signals:
        key = (
            signal["date"],
            signal["direction"],
        )
        grouped[key].append(signal)

    clusters = []

    for (date, direction), signals in grouped.items():

        signals = sorted(
            signals,
            key=lambda x: x["index"],
        )

        current = None

        for signal in signals:

            if current is None:
                current = {
                    "date": date,
                    "direction": direction,
                    "index": signal["index"],
                    "last_index": signal["index"],
                    "time": signal["time"],
                    "entry": signal["entry"],
                    "rules": [signal["rule"]],
                }
                continue

            if (
                signal["index"]
                - current["last_index"]
                <= cluster_gap
            ):
                current["last_index"] = max(
                    current["last_index"],
                    signal["index"],
                )

                if signal["rule"] not in current["rules"]:
                    current["rules"].append(
                        signal["rule"]
                    )

            else:
                current["consensus"] = len(
                    current["rules"]
                )
                clusters.append(current)

                current = {
                    "date": date,
                    "direction": direction,
                    "index": signal["index"],
                    "last_index": signal["index"],
                    "time": signal["time"],
                    "entry": signal["entry"],
                    "rules": [signal["rule"]],
                }

        if current is not None:
            current["consensus"] = len(
                current["rules"]
            )
            clusters.append(current)

    return sorted(
        clusters,
        key=lambda x: (
            x["date"],
            x["index"],
            x["direction"],
        ),
    )


def run_phase4(
    all_signals,
    days,
    dates,
    target_before_stop,
):
    print()
    print("=" * 110)
    print(
        "PHASE-4 MERGED ACTUAL TRADE OPPORTUNITIES"
    )
    print("=" * 110)

    total_test_days = max(
        1,
        len(dates) - 1,
    )

    target_sl_tests = [
        (0.05, 0.05),
        (0.08, 0.05),
        (0.10, 0.05),
        (0.10, 0.08),
        (0.10, 0.10),
        (0.15, 0.10),
        (0.20, 0.10),
    ]

    windows = [
        3,
        5,
        10,
        15,
    ]

    for cluster_gap in (
        0,
        1,
        2,
        3,
    ):

        clusters = merge_signal_clusters(
            all_signals,
            cluster_gap=cluster_gap,
        )

        daily_counts = defaultdict(int)

        consensus_counts = defaultdict(int)

        bullish = 0
        bearish = 0

        for cluster in clusters:

            daily_counts[
                cluster["date"]
            ] += 1

            consensus_counts[
                cluster["consensus"]
            ] += 1

            if (
                cluster["direction"]
                == "BULLISH"
            ):
                bullish += 1
            else:
                bearish += 1

        counts = [
            daily_counts.get(date, 0)
            for date in dates[1:]
        ]

        avg_daily = (
            sum(counts) / len(counts)
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

        days_6_8 = sum(
            1
            for x in counts
            if 6 <= x <= 8
        )

        days_9_plus = sum(
            1
            for x in counts
            if x >= 9
        )

        print()
        print("-" * 110)

        print(
            f"CLUSTER GAP: {cluster_gap} CANDLE"
        )

        print(
            "TOTAL MERGED OPPORTUNITIES:",
            len(clusters),
        )

        print(
            "AVG OPPORTUNITIES/DAY:",
            f"{avg_daily:.2f}",
        )

        print(
            "BULLISH:",
            bullish,
            "| BEARISH:",
            bearish,
        )

        print(
            "ZERO DAYS:",
            zero_days,
            "/",
            total_test_days,
        )

        print(
            "1-2/DAY:",
            days_1_2,
            "| 3-5/DAY:",
            days_3_5,
            "| 6-8/DAY:",
            days_6_8,
            "| 9+/DAY:",
            days_9_plus,
        )

        c1 = consensus_counts.get(
            1,
            0,
        )

        c2 = consensus_counts.get(
            2,
            0,
        )

        c3 = consensus_counts.get(
            3,
            0,
        )

        c4plus = sum(
            count
            for consensus, count
            in consensus_counts.items()
            if consensus >= 4
        )

        print(
            "CONSENSUS 1:",
            c1,
            "| 2:",
            c2,
            "| 3:",
            c3,
            "| 4+:",
            c4plus,
        )

        ranking = []

        for min_consensus in (
            1,
            2,
            3,
            4,
        ):

            selected = [
                cluster
                for cluster in clusters
                if (
                    cluster["consensus"]
                    >= min_consensus
                )
            ]

            if not selected:
                continue

            selected_daily = defaultdict(
                int
            )

            for cluster in selected:
                selected_daily[
                    cluster["date"]
                ] += 1

            sig_per_day = (
                len(selected)
                / total_test_days
            )

            active_days = len(
                selected_daily
            )

            for target_pct, stop_pct in (
                target_sl_tests
            ):

                for window in windows:

                    t = 0
                    s = 0
                    none = 0

                    for cluster in selected:

                        day = days.get(
                            cluster["date"]
                        )

                        if not day:
                            continue

                        outcome = (
                            target_before_stop(
                                day,
                                cluster["index"],
                                cluster["direction"],
                                target_pct,
                                stop_pct,
                                window,
                            )
                        )

                        if outcome == "T":
                            t += 1

                        elif outcome == "S":
                            s += 1

                        else:
                            none += 1

                    resolved = t + s

                    win_rate = (
                        t / resolved * 100
                        if resolved
                        else 0
                    )

                    coverage = (
                        resolved
                        / len(selected)
                        * 100
                        if selected
                        else 0
                    )

                    expectancy = (
                        (
                            t * target_pct
                            - s * stop_pct
                        )
                        / resolved
                        if resolved
                        else 0
                    )

                    ranking.append(
                        (
                            expectancy,
                            win_rate,
                            coverage,
                            sig_per_day,
                            min_consensus,
                            cluster_gap,
                            target_pct,
                            stop_pct,
                            window,
                            len(selected),
                            active_days,
                            t,
                            s,
                            none,
                        )
                    )

        ranking.sort(
            key=lambda x: (
                x[0],
                x[1],
                x[2],
            ),
            reverse=True,
        )

        print()
        print(
            "TOP MERGED TRADE CONFIGURATIONS"
        )

        for rank, item in enumerate(
            ranking[:20],
            1,
        ):

            (
                expectancy,
                win_rate,
                coverage,
                sig_per_day,
                min_consensus,
                gap,
                target_pct,
                stop_pct,
                window,
                signals,
                active_days,
                t,
                s,
                none,
            ) = item

            print(
                f"#{rank:02d} | "
                f"CONS>={min_consensus} | "
                f"GAP {gap}C | "
                f"TGT {target_pct:.2f}% | "
                f"SL {stop_pct:.2f}% | "
                f"{window:2d}C | "
                f"SIG {signals:3d} | "
                f"{sig_per_day:.2f}/DAY | "
                f"ACTIVE {active_days:2d} | "
                f"T {t:3d} | "
                f"S {s:3d} | "
                f"N {none:3d} | "
                f"WIN {win_rate:6.2f}% | "
                f"RES {coverage:6.2f}% | "
                f"EXP {expectancy:+.4f}%"
            )

    print()
    print("=" * 110)
    print(
        "PHASE-4 COMPLETE"
    )
    print("=" * 110)
