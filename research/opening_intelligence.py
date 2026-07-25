import sqlite3
from collections import defaultdict


class OpeningIntelligence:

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

        total_days = 0

        bull_first = 0
        bear_first = 0

        strong_body = 0
        weak_body = 0

        orb_break_up = 0
        orb_break_down = 0

        for day in sorted(days.keys()):

            candles = days[day]

            if len(candles) < 4:
                continue

            total_days += 1

            c1 = candles[0]
            c2 = candles[1]
            c3 = candles[2]

            # First candle direction

            if c1[4] > c1[1]:
                bull_first += 1
            else:
                bear_first += 1

            # Body %

            body = abs(c1[4] - c1[1])
            rng = c1[2] - c1[3]

            if rng > 0:

                body_percent = body * 100 / rng

                if body_percent >= 60:
                    strong_body += 1
                else:
                    weak_body += 1

            # Opening Range Break

            orb_high = max(c1[2], c2[2], c3[2])
            orb_low = min(c1[3], c2[3], c3[3])

            day_high = max(x[2] for x in candles)
            day_low = min(x[3] for x in candles)

            if day_high > orb_high:
                orb_break_up += 1

            if day_low < orb_low:
                orb_break_down += 1

        print("=" * 70)
        print("OPENING INTELLIGENCE ENGINE")
        print("=" * 70)

        print("Trading Days       :", total_days)
        print()

        print("Bull First Candle  :", bull_first)
        print("Bear First Candle  :", bear_first)
        print()

        print("Strong Body        :", strong_body)
        print("Weak Body          :", weak_body)
        print()

        print("ORB Break Up       :", orb_break_up)
        print("ORB Break Down     :", orb_break_down)

        print("=" * 70)

        self.conn.close()


if __name__ == "__main__":
    OpeningIntelligence().run()
