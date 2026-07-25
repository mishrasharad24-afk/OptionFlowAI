from historical.curve_option_backtest import (
    MConnect,
    API_KEY,
    TOKEN_FILE,
    load_contracts,
    fetch_spot_history,
    find_curve_signals,
    find_contract,
    get_option_day,
    TARGET_SL_MATRIX,
    new_matrix_stats,
    check_target_sl,
)


def main():
    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print("=" * 90)
    print("NIFTY CURVE TARGET / SL MATRIX")

    contracts = load_contracts()
    spot_rows = fetch_spot_history(m)
    signals = find_curve_signals(spot_rows)

    print("SPOT CANDLES:", len(spot_rows))
    print("CURVE SIGNALS:", len(signals))

    stats = new_matrix_stats()
    valid = 0
    skipped = 0

    for number, signal in enumerate(signals, 1):

        contract = find_contract(
            contracts,
            signal["date"],
            signal["atm"],
            signal["side"],
        )

        if not contract:
            skipped += 1
            continue

        data = get_option_day(
            m,
            contract,
            signal["date"],
        )

        if not data:
            skipped += 1
            continue

        pos = None

        for i, candle in enumerate(data):
            if candle["dt"] == signal["dt"]:
                pos = i
                break

        if pos is None:
            skipped += 1
            continue

        entry = data[pos]["c"]

        if entry <= 0:
            skipped += 1
            continue

        valid += 1

        print(
            "VALID",
            number,
            "|",
            signal["time"],
            "|",
            signal["side"],
            "| ATM",
            signal["atm"],
            "| ENTRY",
            round(entry, 2),
        )

        for target_pct, sl_pct in TARGET_SL_MATRIX:

            outcome = check_target_sl(
                data,
                pos,
                entry,
                target_pct,
                sl_pct,
            )

            s = stats[
                signal["side"]
            ][
                (target_pct, sl_pct)
            ]

            s["trades"] += 1

            if outcome == "TARGET":
                s["target"] += 1

            elif outcome == "SL":
                s["sl"] += 1

            else:
                s["neither"] += 1

    print("\n" + "=" * 90)
    print("FINAL TARGET / SL MATRIX")
    print("VALID SIGNALS:", valid)
    print("SKIPPED SIGNALS:", skipped)

    for side in ("CE", "PE"):

        print("\nSIDE:", side)

        for target_pct, sl_pct in TARGET_SL_MATRIX:

            s = stats[
                side
            ][
                (target_pct, sl_pct)
            ]

            trades = s["trades"]

            if trades == 0:
                continue

            target_rate = (
                s["target"]
                / trades
                * 100
            )

            sl_rate = (
                s["sl"]
                / trades
                * 100
            )

            print(
                "TARGET",
                target_pct,
                "%",
                "| SL",
                sl_pct,
                "%",
                "| TRADES",
                trades,
                "| TARGET HIT",
                s["target"],
                "| SL HIT",
                s["sl"],
                "| NEITHER",
                s["neither"],
                "| TARGET RATE",
                round(target_rate, 2),
                "%",
                "| SL RATE",
                round(sl_rate, 2),
                "%",
            )


if __name__ == "__main__":
    main()
