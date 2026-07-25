import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.rest_client import RestClient
from core.market_data import MarketData
from core.option_selector import select_atm_options


OPTION_EXCHANGE_ID = {
    "NIFTY": 2,    # NFO
    "SENSEX": 5    # BFO
}


class OptionMarketData:

    def __init__(self):
        self.client = RestClient()

    def get_option_candles(self, index_name, token, interval="minute"):

        exchange_id = OPTION_EXCHANGE_ID[index_name]

        endpoint = (
            f"instruments/intraday/"
            f"{exchange_id}/"
            f"{token}/"
            f"{interval}"
        )

        try:
            response = self.client.get(endpoint)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "http_status": response.status_code,
                    "response": response.text
                }

            return response.json()

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }


if __name__ == "__main__":

    market = MarketData()
    option_market = OptionMarketData()

    for index_name in ["NIFTY", "SENSEX"]:

        spot_data = market.get_candles(index_name)

        candles = spot_data.get(
            "data", {}
        ).get("candles")

        if not candles:
            print(index_name, ": NO SPOT DATA")
            continue

        spot = float(candles[0][4])

        selected = select_atm_options(
            index_name,
            spot
        )

        if not selected:
            print(index_name, ": NO OPTION CONTRACT")
            continue

        print("\n" + "=" * 60)
        print("INDEX :", index_name)
        print("SPOT  :", spot)
        print("ATM   :", selected["atm"])
        print("EXPIRY:", selected["expiry"])

        for option_type in ["ce", "pe"]:

            contract = selected[option_type]

            if not contract:
                print(option_type.upper(), ": CONTRACT NOT FOUND")
                continue

            data = option_market.get_option_candles(
                index_name,
                contract["token"]
            )

            option_candles = data.get(
                "data", {}
            ).get("candles")

            print("\n", option_type.upper())
            print("SYMBOL:", contract["symbol"])
            print("TOKEN :", contract["token"])

            if option_candles:

                latest = option_candles[0]

                print("STATUS: OK")
                print("TOTAL :", len(option_candles))
                print("TIME  :", latest[0])
                print("OPEN  :", latest[1])
                print("HIGH  :", latest[2])
                print("LOW   :", latest[3])
                print("CLOSE :", latest[4])
                print("VOL   :", latest[5])

            else:
                print("STATUS: NO CANDLES")
                print("RAW:", data)
