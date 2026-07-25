import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY


TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"


def test_history(
    m,
    name,
    segment,
    token
):

    print("\n" + "=" * 70)
    print("INDEX   :", name)
    print("SEGMENT :", segment)
    print("TOKEN   :", token)
    print("=" * 70)

    try:

        response = m.get_historical_chart(
            str(segment),
            str(token),
            "5minute",
            "2026-07-01",
            "2026-07-10"
        )

        print(
            "STATUS CODE:",
            response.status_code
        )

        data = response.json()

        candles = (
            data
            .get("data", {})
            .get("candles")
            or []
        )

        if not candles:

            print("NO CANDLES RECEIVED")
            print(data)
            return

        print(
            "STATUS       : OK"
        )

        print(
            "TOTAL CANDLES:",
            len(candles)
        )

        # Sort by timestamp so first/last
        # are shown correctly regardless
        # of API response order.

        candles_sorted = sorted(
            candles,
            key=lambda x: x[0]
        )

        print(
            "FIRST CANDLE :",
            candles_sorted[0]
        )

        print(
            "LAST CANDLE  :",
            candles_sorted[-1]
        )

        unique_dates = sorted(
            set(
                candle[0][:10]
                for candle in candles
            )
        )

        print(
            "TRADING DAYS :",
            len(unique_dates)
        )

        print(
            "DATES        :",
            unique_dates
        )

    except Exception as e:

        print(
            "ERROR:",
            type(e).__name__,
            e
        )


def main():

    if not os.path.exists(
        TOKEN_FILE
    ):

        print(
            "access_token.txt NOT FOUND"
        )

        return

    with open(
        TOKEN_FILE,
        "r"
    ) as f:

        access_token = (
            f.read().strip()
        )

    if not access_token:

        print(
            "ACCESS TOKEN EMPTY"
        )

        return

    m = MConnect(
        api_key=API_KEY,
        access_Token=access_token
    )

    # NSE segment = 1
    # NIFTY token = 26000

    test_history(
        m=m,
        name="NIFTY",
        segment="NSE",
        token="26000"
    )

    # BSE segment = 4
    # SENSEX token = 51

    test_history(
        m=m,
        name="SENSEX",
        segment="BSE",
        token="51"
    )


if __name__ == "__main__":

    main()
