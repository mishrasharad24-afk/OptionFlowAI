from datetime import datetime, timedelta

from historical.collector import HistoricalCollector


class BulkDownloader:

    def __init__(self):

        self.collector = HistoricalCollector()

    def download(
        self,
        exchange,
        token,
        symbol,
        timeframe,
        days=30
    ):

        end = datetime.now()

        for i in range(days):

            start = end - timedelta(days=1)

            print("=" * 50)
            print("Downloading", start.date())

            self.collector.collect(
                exchange=exchange,
                token=token,
                symbol=symbol,
                timeframe=timeframe,
                from_date=start.strftime("%Y-%m-%d 09:15:00"),
                to_date=start.strftime("%Y-%m-%d 15:30:00")
            )

            end = start

