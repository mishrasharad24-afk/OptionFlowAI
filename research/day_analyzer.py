import sqlite3
from collections import defaultdict


class DayAnalyzer:

    def __init__(self, db_path="optionflow.db"):

        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

    def analyze(self):

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

        if not rows:
            print("No Historical Data Found")
            return

        days = defaultdict(list)

        for row in rows:

            dt = row[0].split("T")[0]

            days[dt].append(row)

        bullish = 0
        bearish = 0
        total_range = 0

        print("=" * 60)
        print("AI DAY ANALYZER")
        print("=" * 60)

        for date, candles in days.items():

            day_open = candles[0][1]
            day_close = candles[-1][4]

            day_high = max(x[2] for x in candles)
            day_low = min(x[3] for x in candles)

            rng = day_high - day_low

            total_range += rng

            if day_close > day_open:
                bullish += 1
            else:
                bearish += 1

        total_days = len(days)

        print("Trading Days :", total_days)
        print("Bullish Days :", bullish)
        print("Bearish Days :", bearish)
        print("Average Range:", round(total_range / total_days, 2))

        print("=" * 60)

        self.conn.close()


if __name__ == "__main__":

    DayAnalyzer().analyze()
