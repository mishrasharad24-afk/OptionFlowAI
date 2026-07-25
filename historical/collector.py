from market.historical import MarketHistorical
from database.database import OptionFlowDB


class HistoricalCollector:

    def __init__(self):

        self.market = MarketHistorical()
        self.database = OptionFlowDB()

        self.database.create_tables()

    def collect(
        self,
        exchange,
        token,
        symbol,
        timeframe,
        from_date,
        to_date
    ):

        print("Downloading:", symbol)

        raw_data = self.market.get_candles(
            exchange=exchange,
            token=token,
            interval=timeframe,
            from_date=from_date,
            to_date=to_date
        )

        if not raw_data:
            print("Download Failed")
            return False

        candles = raw_data.get("data", {}).get("candles")

        if not candles:
            print(raw_data)
            print("No candles received")
            return False

        print("Candles:", len(candles))

        for candle in candles:

            self.database.insert_candle(
                symbol,
                timeframe,
                candle
            )

        print("Database Updated")

        return True
