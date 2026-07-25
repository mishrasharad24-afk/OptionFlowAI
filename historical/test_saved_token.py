import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from broker.session import session
from market.historical import MarketHistorical


TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"


def main():

    print("=" * 60)
    print("SAVED TOKEN HISTORICAL API TEST")
    print("=" * 60)

    # ------------------------------------------
    # LOAD SAVED ACCESS TOKEN
    # ------------------------------------------

    if not os.path.exists(TOKEN_FILE):
        print("ERROR: access_token.txt not found")
        return

    with open(TOKEN_FILE, "r") as f:
        access_token = f.read().strip()

    if not access_token:
        print("ERROR: Access token is empty")
        return

    # ------------------------------------------
    # SET TOKEN BEFORE MarketHistorical()
    # ------------------------------------------

    session.set_token(access_token)

    print("Access Token Loaded")

    # Important:
    # MarketHistorical creates MarketClient,
    # which reads token from broker.session.

    market = MarketHistorical()

    # ------------------------------------------
    # TEST OLD SENSEX DATA
    # ------------------------------------------

    try:

        data = market.get_candles(
            exchange="BSE",
            token="51",
            interval="5minute",
            from_date="2024-08-02 09:15:00",
            to_date="2024-08-02 15:30:00"
        )

        candles = (
            data
            .get("data", {})
            .get("candles")
            or []
        )

        print("\n" + "=" * 60)

        if not candles:

            print("NO HISTORICAL CANDLES")
            print(data)
            return

        print("HISTORICAL DATA SUCCESS")
        print("TOTAL CANDLES :", len(candles))

        print("\nFIRST CANDLE:")
        print(candles[-1])

        print("\nLATEST CANDLE:")
        print(candles[0])

    except Exception as e:

        print("\nHISTORICAL TEST FAILED")
        print("ERROR:", e)


if __name__ == "__main__":
    main()
