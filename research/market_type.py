import sqlite3
from collections import defaultdict


class MarketTypeAnalyzer:

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
            print("No Historical Data")
            return

        days = defaultdict(list)

        for row in rows:
            date = row[0].split("T")[0]
            days[date].append(row)

        trend = 0
        reversal = 0
        sideways = 0

        print("=" * 60)
        print("MARKET TYPE ANALYZER")
        print("=" * 60)

        for date, candles in days.items():

            day_open = candles[0][1]
            day_close = candles[-1][4]
            day_high = max(x[2] for x in candles)
            day_low = min(x[3] for x in candles)

            body = abs(day_close - day_open)
            rng = day_high - day_low

            if rng == 0:
                continue

            body_percent = (body / rng) * 100

            if body_percent >= 70:
                trend += 1

            elif body_percent >= 35:
                reversal += 1

            else:
                sideways += 1

        print(f"Trading Days : {len(days)}")
        print(f"Trend Days   : {trend}")
        print(f"Reversal     : {reversal}")
        print(f"Sideways     : {sideways}")

        print("=" * 60)

        self.conn.close()


if __name__ == "__main__":


    MarketTypeAnalyzer().analyze()
