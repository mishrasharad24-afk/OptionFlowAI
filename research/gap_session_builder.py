from datetime import datetime
from collections import defaultdict


class GapSessionBuilder:

    def __init__(self):

        self.days = defaultdict(list)

    def load(self, candles):

        for row in candles:

            ts = datetime.fromisoformat(
                row["timestamp"]
            )

            day = ts.date()

            self.days[day].append(row)

    def build(self):

        result = {}

        previous_close = None

        for day in sorted(self.days.keys()):

            candles = sorted(

                self.days[day],

                key=lambda x: x["timestamp"]

            )

            first = candles[0]

            open_price = first["open"]

            if previous_close is None:

                gap = 0

                gap_type = "NONE"

            else:

                gap = round(

                    ((open_price - previous_close)

                    / previous_close) * 100,

                    2

                )

                if gap > 0.15:

                    gap_type = "GAP_UP"

                elif gap < -0.15:

                    gap_type = "GAP_DOWN"

                else:

                    gap_type = "FLAT"

            previous_close = candles[-1]["close"]

            result[day] = {

                "gap_pct": gap,

                "gap_type": gap_type,

                "open": open_price,

                "previous_close": previous_close

            }

        return result


if __name__ == "__main__":

    from historical_reader import HistoricalReader

    reader = HistoricalReader()

    candles = reader.load()

    engine = GapSessionBuilder()

    engine.load(candles)

    data = engine.build()

    print("=" * 60)

    print("GAP SESSION BUILDER")

    print("=" * 60)

    print("Trading Days :", len(data))

    print()

    first = sorted(data.keys())[0]

    print(first)

    print(data[first])

    print("=" * 60)

    reader.close()
