import sqlite3
from collections import defaultdict


class TradeOutcome:

    def __init__(self, db="optionflow.db"):
        self.conn = sqlite3.connect(db)
        self.cur = self.conn.cursor()

    def run(self):

        self.cur.execute("""
        SELECT timestamp,open,high,low,close
        FROM historical_data
        WHERE symbol='SENSEX'
        AND timeframe='5minute'
        ORDER BY timestamp
        """)

        rows = self.cur.fetchall()

        if not rows:
            print("No Data")
            return

        days = defaultdict(list)

        for row in rows:
            day = row[0].split("T")[0]
            days[day].append(row)

        target30 = 0
        target50 = 0
        target100 = 0

        total = 0

        print("=" * 70)
        print("TRADE OUTCOME ENGINE")
        print("=" * 70)

        for day in sorted(days.keys()):

            candles = days[day]

            entry = candles[0][1]

            day_high = max(x[2] for x in candles)
            day_low = min(x[3] for x in candles)

            up_move = day_high - entry
            down_move = entry - day_low

            total += 1

            if up_move >= 30:
                target30 += 1

            if up_move >= 50:
                target50 += 1

            if up_move >= 100:
                target100 += 1

        print("Trading Days :", total)
        print()
        print("Target 30 Hit :", target30)
        print("Target 50 Hit :", target50)
        print("Target100 Hit :", target100)

        print("=" * 70)

        self.conn.close()


if __name__ == "__main__":
    TradeOutcome().run()
