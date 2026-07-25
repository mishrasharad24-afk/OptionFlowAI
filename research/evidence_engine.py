import sqlite3
from collections import defaultdict


class EvidenceEngine:

    def __init__(self, db_path="optionflow.db"):

        self.conn = sqlite3.connect(db_path)
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

        if not rows:
            print("No Historical Data")
            return

        days = defaultdict(list)

        for row in rows:
            date = row[0].split("T")[0]
            days[date].append(row)

        previous = None

        pdh_break = 0
        pdh_win = 0

        pdl_break = 0
        pdl_win = 0

        gap_up = 0
        gap_up_bull = 0

        gap_down = 0
        gap_down_bear = 0

        for date in sorted(days.keys()):

            candles = days[date]

            day_open = candles[0][1]
            day_close = candles[-1][4]
            day_high = max(x[2] for x in candles)
            day_low = min(x[3] for x in candles)

            bullish = day_close > day_open

            if previous:

                if day_open > previous["close"]:
                    gap_up += 1
                    if bullish:
                        gap_up_bull += 1

                elif day_open < previous["close"]:
                    gap_down += 1
                    if not bullish:
                        gap_down_bear += 1

                if day_high > previous["high"]:
                    pdh_break += 1
                    if bullish:
                        pdh_win += 1

                if day_low < previous["low"]:
                    pdl_break += 1
                    if not bullish:
                        pdl_win += 1

            previous = {
                "high": day_high,
                "low": day_low,
                "close": day_close
            }

        print("=" * 70)
        print("EVIDENCE ENGINE")
        print("=" * 70)

        print(f"PDH Break      : {pdh_break}   Bullish : {pdh_win}")
        print(f"PDL Break      : {pdl_break}   Bearish : {pdl_win}")
        print(f"Gap Up         : {gap_up}   Bullish : {gap_up_bull}")
        print(f"Gap Down       : {gap_down}   Bearish : {gap_down_bear}")

        print("=" * 70)

        self.conn.close()


if __name__ == "__main__":
    EvidenceEngine().run()
