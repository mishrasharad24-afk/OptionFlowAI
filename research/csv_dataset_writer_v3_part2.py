from datetime import datetime

from csv_dataset_writer_v3_part1 import DatasetContext
from feature_row_builder_v2 import FeatureRowBuilderV2


class DatasetGenerator:

    def __init__(self):

        self.ctx = DatasetContext()

    def build(self):

        self.ctx.load()

        rows = []

        candles = self.ctx.candles

        for i in range(50, len(candles)):

            window = candles[i-50:i+1]

            day = datetime.fromisoformat(
                candles[i]["timestamp"]
            ).date()

            if day not in self.ctx.gap_session:
                continue

            if day not in self.ctx.orb_session:
                continue

            row = FeatureRowBuilderV2.build(

                window,

                self.ctx.gap_session,

                self.ctx.orb_session,

                day

            )

            if row:

                row["timestamp"] = candles[i]["timestamp"]

                row["symbol"] = candles[i]["symbol"]

                rows.append(row)

        return rows

    def close(self):

        self.ctx.close()


if __name__ == "__main__":

    app = DatasetGenerator()

    rows = app.build()

    print("=" * 60)
    print("DATASET GENERATOR")
    print("=" * 60)

    print("Rows :", len(rows))

    print()

    print(rows[0])

    print()

    print(rows[-1])

    print("=" * 60)

    app.close()
