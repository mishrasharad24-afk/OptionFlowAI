import sqlite3
from collections import defaultdict
import csv


class FeatureBuilder:

    def __init__(self, db="optionflow.db"):
        self.conn = sqlite3.connect(db)
        self.cur = self.conn.cursor()

    def run(self):

        self.cur.execute("""
        SELECT
            timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM historical_data
        WHERE symbol='SENSEX'
        AND timeframe='5minute'
        ORDER BY timestamp
        """)

        rows = self.cur.fetchall()

        days = defaultdict(list)

        for row in rows:
            day = row[0].split("T")[0]
            days[day].append(row)

        previous = None

        with open("training_dataset.csv", "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([
                "date",
                "gap_pct",
                "first_body_pct",
                "first_range",
                "orb_range",
                "day_range",
                "bull_first",
                "bear_first",
                "pdh_break",
                "pdl_break",
                "day_result"
            ])

            for day in sorted(days.keys()):

                candles = days[day]

                if len(candles) < 3:
                    continue

                first = candles[0]
                second = candles[1]
                third = candles[2]

                day_high = max(x[2] for x in candles)
                day_low = min(x[3] for x in candles)

                day_open = first[1]
                day_close = candles[-1][4]

                bull = 1 if first[4] > first[1] else 0
                bear = 1 if first[4] < first[1] else 0

                rng = first[2] - first[3]
                body = abs(first[4] - first[1])

                body_pct = 0
                if rng > 0:
                    body_pct = round(body * 100 / rng, 2)

                orb_high = max(first[2], second[2], third[2])
                orb_low = min(first[3], second[3], third[3])

                orb_range = round(orb_high - orb_low, 2)
                day_range = round(day_high - day_low, 2)

                gap = 0
                pdh_break = 0
                pdl_break = 0

                if previous:

                    gap = round(
                        ((day_open - previous["close"]) / previous["close"]) * 100,
                        2
                    )

                    if day_high > previous["high"]:
                        pdh_break = 1

                    if day_low < previous["low"]:
                        pdl_break = 1

                if day_close > day_open:
                    result = "BULL"
                elif day_close < day_open:
                    result = "BEAR"
                else:
                    result = "SIDE"

                writer.writerow([
                    day,
                    gap,
                    body_pct,
                    round(rng, 2),
                    orb_range,
                    day_range,
                    bull,
                    bear,
                    pdh_break,
                    pdl_break,
                    result
                ])

                previous = {
                    "high": day_high,
                    "low": day_low,
                    "close": day_close
                }

        print("=" * 60)
        print("FEATURE DATASET CREATED")
        print("=" * 60)
        print("Output : training_dataset.csv")
        print("Trading Days :", len(days))
        print("=" * 60)

        self.conn.close()


if __name__ == "__main__":
    FeatureBuilder().run()
