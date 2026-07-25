import sqlite3
from collections import defaultdict


class CombinationEngine:

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

        patterns = {}

        for date in sorted(days.keys()):

            candles = days[date]

            day_open = candles[0][1]
            day_close = candles[-1][4]
            day_high = max(x[2] for x in candles)
            day_low = min(x[3] for x in candles)

            bullish = day_close > day_open

            if previous:

                evidence = []

                if day_open > previous["close"]:
                    evidence.append("GapUp")

                elif day_open < previous["close"]:
                    evidence.append("GapDown")

                if day_high > previous["high"]:
                    evidence.append("PDH")

                if day_low < previous["low"]:
                    evidence.append("PDL")

                first15_high = max(x[2] for x in candles[:3])
                first15_low = min(x[3] for x in candles[:3])

                if day_close > first15_high:
                    evidence.append("ORB_Bull")

                elif day_close < first15_low:
                    evidence.append("ORB_Bear")

                key = " + ".join(sorted(evidence))

                if key:

                    if key not in patterns:
                        patterns[key] = {
                            "count": 0,
                            "bull": 0,
                            "bear": 0
                        }

                    patterns[key]["count"] += 1

                    if bullish:
                        patterns[key]["bull"] += 1
                    else:
                        patterns[key]["bear"] += 1

            previous = {
                "high": day_high,
                "low": day_low,
                "close": day_close
            }

        print("=" * 80)
        print("COMBINATION ENGINE")
        print("=" * 80)

        for name, stat in sorted(patterns.items(),
                                 key=lambda x: x[1]["count"],
                                 reverse=True):

            total = stat["count"]
            bull = stat["bull"]
            bear = stat["bear"]

            win = max(bull, bear) * 100 / total

            print()
            print(name)
            print("Occurrences :", total)
            print("Bullish     :", bull)
            print("Bearish     :", bear)
            print("Strength    : {:.1f}%".format(win))

        print("=" * 80)

        self.conn.close()


if __name__ == "__main__":
    CombinationEngine().run()
