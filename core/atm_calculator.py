import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.market_data import MarketData


# Strike intervals
STRIKE_GAP = {
    "NIFTY": 50,
    "SENSEX": 100
}


def calculate_atm(spot, strike_gap):
    return round(spot / strike_gap) * strike_gap


def get_latest_spot(candles):
    if not candles:
        return None

    # API returns latest candle first
    return float(candles[0][4])


if __name__ == "__main__":

    market = MarketData()

    for index in ["NIFTY", "SENSEX"]:

        data = market.get_candles(index)

        if data.get("status") != "success":
            print(f"{index}: DATA ERROR")
            continue

        candles = data.get("data", {}).get("candles")

        spot = get_latest_spot(candles)

        if spot is None:
            print(f"{index}: NO SPOT DATA")
            continue

        gap = STRIKE_GAP[index]

        atm = calculate_atm(
            spot,
            gap
        )

        print("=" * 50)
        print("INDEX :", index)
        print("SPOT  :", spot)
        print("ATM   :", atm)
        print("CE    :", f"{atm} CE")
        print("PE    :", f"{atm} PE")
