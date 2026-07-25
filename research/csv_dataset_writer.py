import csv

from historical_reader import HistoricalReader


class CSVDatasetWriter:

    def __init__(self):

        self.reader = HistoricalReader()

    def build(self, output_file="training_dataset_v2.csv"):

        rows = self.reader.load()

        if not rows:

            print("No Historical Data Found")
            return

        with open(output_file, "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([
                "timestamp",
                "symbol",
                "timeframe",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ])

            for row in rows:

                writer.writerow([

                    row["timestamp"],

                    row["symbol"],

                    row["timeframe"],

                    row["open"],

                    row["high"],

                    row["low"],

                    row["close"],

                    row["volume"]

                ])

        print("=" * 60)
        print("CSV DATASET CREATED")
        print("=" * 60)
        print("Rows :", len(rows))
        print("File :", output_file)
        print("=" * 60)

        self.reader.close()


if __name__ == "__main__":

    writer = CSVDatasetWriter()

    writer.build()
