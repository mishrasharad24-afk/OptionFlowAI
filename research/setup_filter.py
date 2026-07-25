import sqlite3
from collections import defaultdict


class SetupFilter:

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
            close
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

        trades = 0
        skipped = 0

        wins = 0
        losses = 0

        TARGET = 80
        SL = 40

        print("=" * 70)
        print("SETUP FILTER ENGINE")
        print("=" * 70)

        for day in sorted(days.keys()):

            candles = days[day]

            if len(candles) < 6:
                continue

            if previous is None:

                previous = {
                    "high": max(x[2] for x in candles),
                    "low": max(x[3] for x in candles),
                    "close": candles[-1][4]
                }

                continue

            first15_high = max(x[2] for x in candles[:3])

            entry_candle = candles[3]

            entry = entry_candle[1]

            body = abs(entry_candle[4] - entry_candle[1])

            rng = entry_candle[2] - entry_candle[3]

            if rng == 0:
                continue

            body_percent = body * 100 / rng

            setup = (
                entry_candle[4] > first15_high and
                max(x[2] for x in candles) > previous["high"] and
                body_percent >= 60
            )

            if not setup:

                skipped += 1

                previous = {
                    "high": max(x[2] for x in candles),
                    "low": min(x[3] for x in candles),
                    "close": candles[-1][4]
                }

                continue

            trades += 1

            target = entry + TARGET
            stop = entry - SL

            result = None

            for c in candles[4:]:

                if c[3] <= stop:
                    result = "LOSS"
                    break

                if c[2] >= target:
                    result = "WIN"
                    break

            if result == "WIN":
                wins += 1
            else:
                losses += 1

            previous = {
                "high": max(x[2] for x in candles),
                "low": min(x[3] for x in candles),
                "close": candles[-1][4]
            }

        print("Trading Days :", len(days))
        print("Trades Taken :", trades)
        print("Days Skipped :", skipped)
        print()
        print("Wins         :", wins)
        print("Losses       :", losses)

        if trades:

            print("Win Rate     : {:.2f}%".format(
                wins * 100 / trades
            ))

        print("=" * 70)

        self.conn.close()


if __name__ == "__main__":
    SetupFilter().run()
