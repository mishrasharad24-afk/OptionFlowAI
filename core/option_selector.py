import sys
import os
import csv
from datetime import date, datetime

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.market_data import MarketData


MASTER_FILE = "instrument_master.csv"

INDEX_CONFIG = {
    "NIFTY": {
        "exchange": "NFO",
        "strike_gap": 50
    },
    "SENSEX": {
        "exchange": "BFO",
        "strike_gap": 100
    }
}


def calculate_atm(spot, gap):
    return round(spot / gap) * gap


def load_option_contracts(index_name):

    config = INDEX_CONFIG[index_name]
    exchange = config["exchange"]

    contracts = []

    with open(MASTER_FILE, "r", errors="ignore") as f:

        reader = csv.reader(f)

        for row in reader:

            if len(row) < 12:
                continue

            try:

                underlying = row[3].strip()
                expiry_text = row[5].strip()
                strike_text = row[6].strip()
                option_type = row[9].strip()
                instrument_type = row[10].strip()
                row_exchange = row[11].strip()

                if underlying != index_name:
                    continue

                if row_exchange != exchange:
                    continue

                if instrument_type != "OPTIDX":
                    continue

                if option_type not in ("CE", "PE"):
                    continue

                expiry = datetime.strptime(
                    expiry_text,
                    "%Y-%m-%d"
                ).date()

                strike = int(float(strike_text))

                contracts.append({
                    "token": row[0].strip(),
                    "symbol": row[2].strip(),
                    "expiry": expiry,
                    "strike": strike,
                    "type": option_type,
                    "exchange": row_exchange
                })

            except Exception:
                continue

    return contracts


def select_atm_options(index_name, spot):

    config = INDEX_CONFIG[index_name]

    atm = calculate_atm(
        spot,
        config["strike_gap"]
    )

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

    selected = [
        c for c in contracts
        if c["expiry"] == nearest_expiry
        and c["strike"] == atm
    ]

    ce = next(
        (c for c in selected if c["type"] == "CE"),
        None
    )

    pe = next(
        (c for c in selected if c["type"] == "PE"),
        None
    )

    return {
        "index": index_name,
        "spot": spot,
        "atm": atm,
        "expiry": nearest_expiry,
        "ce": ce,
        "pe": pe
    }


if __name__ == "__main__":

    market = MarketData()

    for index_name in ["NIFTY", "SENSEX"]:

        data = market.get_candles(index_name)

        candles = data.get(
            "data", {}
        ).get("candles")

        if not candles:
            print(index_name, ": NO MARKET DATA")
            continue

        spot = float(candles[0][4])

        result = select_atm_options(
            index_name,
            spot
        )

        print("\n" + "=" * 60)

        if result is None:

            print(index_name, ": NO VALID OPTION CONTRACT")

        else:

            print("INDEX  :", result["index"])
            print("SPOT   :", result["spot"])
            print("ATM    :", result["atm"])
            print("EXPIRY :", result["expiry"])

            print("\nCE:")
            print(result["ce"])

            print("\nPE:")
            print(result["pe"])
