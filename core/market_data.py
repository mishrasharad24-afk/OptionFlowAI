import sys
import os
import json

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.rest_client import RestClient


# ==========================================
# INDEX CONFIGURATION
# ==========================================

INDICES = {
    "NIFTY": {
        "exchange": 1,      # NSE
        "token": 26000,
        "interval": "minute"
    },

    "SENSEX": {
        "exchange": 4,      # BSE
        "token": 51,
        "interval": "minute"
    }
}


# ==========================================
# MARKET DATA ENGINE
# ==========================================

class MarketData:

    def __init__(self):
        self.client = RestClient()

    def get_candles(self, index_name, interval=None):

        index_name = index_name.upper()

        if index_name not in INDICES:
            return {
                "status": "error",
                "message": f"Unknown index: {index_name}"
            }

        config = INDICES[index_name]

        exchange = config["exchange"]
        token = config["token"]

        if interval is None:
            interval = config["interval"]

        endpoint = (
            f"instruments/intraday/"
            f"{exchange}/"
            f"{token}/"
            f"{interval}"
        )

        try:

            response = self.client.get(endpoint)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "index": index_name,
                    "http_status": response.status_code,
                    "response": response.text
                }

            return response.json()

        except Exception as e:

            return {
                "status": "error",
                "index": index_name,
                "message": str(e)
            }


# ==========================================
# TEST BOTH INDICES
# ==========================================

if __name__ == "__main__":

    market = MarketData()

    for index in ["NIFTY", "SENSEX"]:

        print("\n" + "=" * 60)
        print(index)
        print("=" * 60)

        data = market.get_candles(index)

        if data.get("status") == "success":

            candles = data.get("data", {}).get("candles")

            if candles:

                print("STATUS: OK")
                print("TOTAL CANDLES:", len(candles))

                # API returns newest candle first
                latest = candles[0]

                print("LATEST CANDLE:")
                print("Time :", latest[0])
                print("Open :", latest[1])
                print("High :", latest[2])
                print("Low  :", latest[3])
                print("Close:", latest[4])
                print("Vol  :", latest[5])

            else:
                print("STATUS: NO CANDLES")

        else:

            print("STATUS: ERROR")
            print(json.dumps(data, indent=4))
