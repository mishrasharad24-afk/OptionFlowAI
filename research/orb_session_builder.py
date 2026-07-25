from datetime import datetime
from collections import defaultdict


class ORBSessionBuilder:

    def __init__(self):

        self.sessions = defaultdict(list)

    def load(self, candles):

        for row in candles:

            ts = datetime.fromisoformat(
                row["timestamp"]
            )

            day = ts.date()

            self.sessions[day].append(row)

    def build(self):

        result = {}

        for day, rows in self.sessions.items():

            rows.sort(
                key=lambda x: x["timestamp"]
            )

            opening = rows[:3]

            if len(opening) == 0:
                continue

            orb_high = max(
                x["high"] for x in opening
            )

            orb_low = min(
                x["low"] for x in opening
            )

            result[day] = {

                "orb_high": orb_high,

                "orb_low": orb_low

            }

        return result


if __name__ == "__main__":

    from historical_reader import HistoricalReader

    reader = HistoricalReader()

    candles = reader.load()

    orb = ORBSessionBuilder()

    orb.load(candles)

    sessions = orb.build()

    print("=" * 60)

    print("ORB SESSION BUILDER")

    print("=" * 60)

    print("Trading Days :", len(sessions))

    print()

    first = list(sessions.items())[0]

    print(first)

    reader.close()
