import sqlite3
from collections import defaultdict


class MarketStructure:

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

        previous_day = None

        print("=" * 70)
        print("MARKET STRUCTURE ANALYZER")
        print("=" * 70)

        trend = 0
        gap_up = 0
        gap_down = 0

        for date in sorted(days.keys()):

            candles = days[date]

            day_open = candles[0][1]
            day_close = candles[-1][4]

            day_high = max(x[2] for x in candles)
            day_low = min(x[3] for x in candles)

            first15_high = max(x[2] for x in candles[:3])
            first15_low = min(x[3] for x in candles[:3])

            if previous_day:

                prev_high = previous_day["high"]
                prev_low = previous_day["low"]
                prev_close = previous_day["close"]

                if day_open > prev_close:
                    gap_up += 1

                elif day_open < prev_close:
                    gap_down += 1

                evidence = []

                if day_high > prev_high:
                    evidence.append("PDH Break")

                if day_low < prev_low:
                    evidence.append("PDL Break")

                if day_close > first15_high:
                    evidence.append("ORB Bullish")

                elif day_close < first15_low:
                    evidence.append("ORB Bearish")

                if len(evidence) >= 2:
                    trend += 1

            previous_day = {
                "high": day_high,
                "low": day_low,
                "close": day_close
            }

        print("Trading Days :", len(days))
        print("Trend Days   :", trend)
        print("Gap Up Days  :", gap_up)
        print("Gap Down Days:", gap_down)

        print("=" * 70)

        self.conn.close()


if __name__ == "__main__":

    MarketStructure().analyze()
