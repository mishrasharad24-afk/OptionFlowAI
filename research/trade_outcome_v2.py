import sqlite3
from collections import defaultdict


class TradeOutcomeV2:

    def __init__(self, db="optionflow.db"):

        self.conn = sqlite3.connect(db)
        self.cur = self.conn.cursor()

    def load_days(self):

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

        return days

    def simulate(self):

        days = self.load_days()

        wins = 0
        losses = 0
        no_result = 0

        TARGET = 80
        SL = 40

        print("=" * 70)
        print("TRADE OUTCOME ENGINE V2")
        print("=" * 70)

        for day in sorted(days.keys()):

            candles = days[day]

            if len(candles) < 4:
                continue

            entry = candles[3][1]

            target = entry + TARGET
            stop = entry - SL

            result = None

            for candle in candles[4:]:

                high = candle[2]
                low = candle[3]

                if low <= stop:
                    result = "LOSS"
                    break

                if high >= target:
                    result = "WIN"
                    break

            if result == "WIN":
                wins += 1

            elif result == "LOSS":
                losses += 1

            else:
                no_result += 1

        total = wins + losses + no_result

        print("Trading Days :", total)
        print()

        print("Wins         :", wins)
        print("Losses       :", losses)
        print("No Result    :", no_result)

        if total > 0:

            print()
            print("Win Rate     : {:.2f}%".format(
                wins * 100 / total
            ))

        print("=" * 70)

        self.conn.close()


if __name__ == "__main__":

    TradeOutcomeV2().simulate()
