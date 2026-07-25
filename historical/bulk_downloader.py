import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from historical.collector import HistoricalCollector


class BulkDownloader:

    def __init__(self):

        self.collector = HistoricalCollector()
        self.progress_file = "progress.json"

    def save_progress(self, dt):

        with open(self.progress_file, "w") as f:

            json.dump(
                {
                    "last_date": dt.strftime("%Y-%m-%d")
                },
                f
            )

    def load_progress(self):

        if not Path(self.progress_file).exists():
            return None

        with open(self.progress_file, "r") as f:

            return json.load(f)

    def download(
        self,
        exchange,
        token,
        symbol,
        timeframe,
        end_date,
        days=365
    ):

        progress = self.load_progress()

        if progress:

            current = datetime.strptime(
                progress["last_date"],
                "%Y-%m-%d"
            )

        else:

            current = datetime.strptime(
                end_date,
                "%Y-%m-%d"
            )

        print("=" * 60)
        print("Starting Bulk Download")
        print("Symbol :", symbol)
        print("Start  :", current.strftime("%Y-%m-%d"))
        print("Days   :", days)
        print("=" * 60)
        for _ in range(days):

            from_date = current.strftime("%Y-%m-%d") + " 09:15:00"
            to_date = current.strftime("%Y-%m-%d") + " 15:30:00"

            print("=" * 60)
            print("Downloading :", current.strftime("%Y-%m-%d"))

            try:

                success = self.collector.collect(
                    exchange=exchange,
                    token=token,
                    symbol=symbol,
                    timeframe=timeframe,
                    from_date=from_date,
                    to_date=to_date
                )

                if success:

                    self.save_progress(current)

                    print(
                        "Saved :",
                        current.strftime("%Y-%m-%d")
                    )

                else:

                    print(
                        "Skipped :",
                        current.strftime("%Y-%m-%d")
                    )

            except Exception as e:

                print("Error :", e)

                print("Retry after 2 seconds...")

                time.sleep(2)

                continue
            current = current - timedelta(days=1)

            # Weekend skip
            while current.weekday() >= 5:
                print(
                    "Weekend Skip :",
                    current.strftime("%Y-%m-%d")
                )
                current = current - timedelta(days=1)

        print("=" * 60)
        print("Bulk Historical Download Completed")
        print("=" * 60)

        return True
