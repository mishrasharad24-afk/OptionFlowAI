from collections import Counter

from historical.curve_option_backtest import (
    MConnect,
    API_KEY,
    TOKEN_FILE,
    load_contracts,
    fetch_spot_history,
    find_curve_signals,
    find_contract,
    get_option_day,
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
    print("NIFTY CURVE SKIP DIAGNOSTIC")

    contracts = load_contracts()
    spot_rows = fetch_spot_history(m)
    signals = find_curve_signals(spot_rows)

    reasons = Counter()
    valid = 0

    print("CONTRACTS:", len(contracts))
    print("SPOT CANDLES:", len(spot_rows))
    print("CURVE SIGNALS:", len(signals))

    for number, signal in enumerate(signals, 1):

        contract = find_contract(
            contracts,
            signal["date"],
            signal["atm"],
            signal["side"],
        )

        if not contract:
            reasons["NO_CONTRACT"] += 1

            print(
                "SKIP",
                number,
                "| NO_CONTRACT",
                "| DATE", signal["date"],
                "|", signal["side"],
                "| ATM", signal["atm"],
            )
            continue

        try:
            data = get_option_day(
                m,
                contract,
                signal["date"],
            )

        except Exception as e:
            reasons["OPTION_API_ERROR"] += 1

            print(
                "SKIP",
                number,
                "| OPTION_API_ERROR",
                "|", contract["symbol"],
                "|", type(e).__name__,
                e,
            )
            continue

        if not data:
            reasons["NO_OPTION_DATA"] += 1

            print(
                "SKIP",
                number,
                "| NO_OPTION_DATA",
                "| DATE", signal["date"],
                "|", contract["symbol"],
                "| TOKEN", contract["token"],
            )
            continue

        timestamps = {
            candle["dt"]
            for candle in data
        }

        if signal["dt"] not in timestamps:
            reasons["TIMESTAMP_MISSING"] += 1

            print(
                "SKIP",
                number,
                "| TIMESTAMP_MISSING",
                "| SIGNAL", signal["time"],
                "|", contract["symbol"],
                "| OPTION CANDLES", len(data),
            )
            continue

        valid += 1
        reasons["VALID"] += 1

    print("\n" + "=" * 90)
    print("DIAGNOSTIC SUMMARY")

    for reason, count in reasons.most_common():
        print(
            reason,
            ":",
            count
        )

    print(
        "\nTOTAL SIGNALS:",
        len(signals)
    )

    print(
        "VALID:",
        valid
    )

    print(
        "TOTAL SKIPPED:",
        len(signals) - valid
    )


if __name__ == "__main__":
    main()
