import sys
import os
from datetime import date

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.market_data import MarketData
from core.option_selector import (
    calculate_atm,
    load_option_contracts,
    INDEX_CONFIG
)


def select_nearby_options(index_name, spot, wings=2):

    config = INDEX_CONFIG[index_name]
    gap = config["strike_gap"]

    atm = calculate_atm(spot, gap)

    # ATM -2, -1, ATM, +1, +2
    target_strikes = [
        atm + (i * gap)
        for i in range(-wings, wings + 1)
    ]

    contracts = load_option_contracts(index_name)

    today = date.today()

    valid_expiries = sorted(
        set(
            c["expiry"]
            for c in contracts
            if c["expiry"] >= today
        )
    )

    if not valid_expiries:
        return None

    nearest_expiry = valid_expiries[0]

    result = []

    for strike in target_strikes:

        ce = next(
            (
                c for c in contracts
                if c["expiry"] == nearest_expiry
                and c["strike"] == strike
                and c["type"] == "CE"
            ),
            None
        )

        pe = next(
            (
                c for c in contracts
                if c["expiry"] == nearest_expiry
                and c["strike"] == strike
                and c["type"] == "PE"
            ),
            None
        )

        result.append({
            "strike": strike,
            "ce": ce,
            "pe": pe
        })

    return {
        "index": index_name,
        "spot": spot,
        "atm": atm,
        "expiry": nearest_expiry,
        "strikes": result
    }


if __name__ == "__main__":

    market = MarketData()

    for index_name in ["NIFTY", "SENSEX"]:

        data = market.get_candles(index_name)

        candles = data.get(
            "data", {}
        ).get("candles")

        if not candles:
            print(index_name, ": NO SPOT DATA")
            continue

        spot = float(candles[0][4])

        result = select_nearby_options(
            index_name,
            spot,
            wings=2
        )

        print("\n" + "=" * 70)

        if not result:
            print(index_name, ": NO OPTIONS")
            continue

        print("INDEX  :", result["index"])
        print("SPOT   :", result["spot"])
        print("ATM    :", result["atm"])
        print("EXPIRY :", result["expiry"])

        print("\nSTRIKE | CE TOKEN | PE TOKEN")
        print("-" * 45)

        for item in result["strikes"]:

            ce_token = (
                item["ce"]["token"]
                if item["ce"]
                else "NOT FOUND"
            )

            pe_token = (
                item["pe"]["token"]
                if item["pe"]
                else "NOT FOUND"
            )

            atm_tag = (
                " <-- ATM"
                if item["strike"] == result["atm"]
                else ""
            )

            print(
                f'{item["strike"]} | '
                f'{ce_token} | '
                f'{pe_token}'
                f'{atm_tag}'
            )
