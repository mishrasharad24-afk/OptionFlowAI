import sys
import os
from datetime import datetime

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.market_data import MarketData


def get_candles(data):
    return data.get("data", {}).get("candles") or []


def parse_datetime(timestamp):
    try:
        return datetime.fromisoformat(timestamp)
    except Exception:
        return None


def check_range(index_name, market):

    data = market.get_candles(index_name)

    candles = get_candles(data)

    if not candles:
        print(index_name, ": NO DATA")
        return

    dates = []

    for candle in candles:

        dt = parse_datetime(candle[0])

        if dt:
            dates.append(dt)

    if not dates:
        print(index_name, ": INVALID DATE DATA")
        return

    dates.sort()

    unique_days = sorted(
        set(dt.date() for dt in dates)
    )

    print("\n" + "=" * 60)

    print("INDEX         :", index_name)
    print("TOTAL CANDLES :", len(candles))
    print("FIRST CANDLE  :", dates[0])
    print("LAST CANDLE   :", dates[-1])
    print("TRADING DAYS  :", len(unique_days))

    print("\nFIRST 5 DAYS:")

    for day in unique_days[:5]:
        print("-", day)

    print("\nLAST 5 DAYS:")

    for day in unique_days[-5:]:
        print("-", day)


def main():

    market = MarketData()

    for index_name in [
        "NIFTY",
        "SENSEX"
    ]:

        check_range(
            index_name,
            market
        )


if __name__ == "__main__":
    main()
