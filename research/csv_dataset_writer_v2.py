import csv

from historical_reader import HistoricalReader
from feature_row_builder import FeatureRowBuilder


class CSVDatasetWriterV2:

    def __init__(self):

        self.reader = HistoricalReader()

    def build(self,
              output_file="training_dataset_v2.csv"):

        candles = self.reader.load()

        if len(candles) < 50:

            print("Not Enough Data")
            return

        total = 0

        with open(output_file, "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([

                "timestamp",

                "symbol",

                "gap_pct",
                "gap_type",
                "gap_strength",
                "gap_bias",

                "body_pct",
                "upper_wick_pct",
                "lower_wick_pct",
                "opening_strength",

                "orb_range",
                "orb_strength",
                "orb_break",
                "orb_hold",

                "ema20",
                "ema50",
                "trend",

                "atr",

                "pdh",
                "pdl",
                "pdh_status"

            ])

            for i in range(50, len(candles)):

                window = candles[i-50:i+1]

                row = FeatureRowBuilder.build(window)

                if row is None:

                    continue

                writer.writerow([

                    candles[i]["timestamp"],

                    candles[i]["symbol"],

                    row.get("gap_pct"),
                    row.get("gap_type"),
                    row.get("gap_strength"),
                    row.get("gap_bias"),

                    row.get("body_pct"),
                    row.get("upper_wick_pct"),
                    row.get("lower_wick_pct"),
                    row.get("opening_strength"),

                    row.get("orb_range"),
                    row.get("orb_strength"),
                    row.get("orb_break"),
                    row.get("orb_hold"),

                    row.get("ema20"),
                    row.get("ema50"),
                    row.get("trend"),

                    row.get("atr"),

                    row.get("pdh"),
                    row.get("pdl"),
                    row.get("pdh_status")

                ])

                total += 1

        self.reader.close()

        print("=" * 60)
        print("AI DATASET CREATED")
        print("=" * 60)
        print("Rows :", total)
        print("File :", output_file)
        print("=" * 60)


if __name__ == "__main__":

    app = CSVDatasetWriterV2()

    app.build()
