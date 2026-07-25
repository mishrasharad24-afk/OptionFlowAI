from config.settings import HISTORICAL_URL
from market.client import MarketClient


class MarketHistorical:

    def __init__(self):
        self.client = MarketClient()

    def get_candles(
        self,
        exchange,
        token,
        interval,
        from_date,
        to_date
    ):

        endpoint = HISTORICAL_URL.format(
            segment=exchange,
            token=token,
            interval=interval
        )

        params = {
            "from": from_date,
            "to": to_date
        }

        print("=" * 60)
        print("Endpoint :", endpoint)
        print("Params   :", params)

        response = self.client.get(
            endpoint,
            params=params
        )

        print("Status Code :", response.status_code)
        print("Response    :", response.text)

        return response.json()
