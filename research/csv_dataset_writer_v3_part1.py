from historical_reader import HistoricalReader
from gap_session_builder import GapSessionBuilder
from orb_session_builder import ORBSessionBuilder


class DatasetContext:

    def __init__(self):

        self.reader = HistoricalReader()

        self.candles = []

        self.gap_session = {}

        self.orb_session = {}

    def load(self):

        self.candles = self.reader.load()

        gap = GapSessionBuilder()
        gap.load(self.candles)
        self.gap_session = gap.build()

        orb = ORBSessionBuilder()
        orb.load(self.candles)
        self.orb_session = orb.build()

    def close(self):

        self.reader.close()


if __name__ == "__main__":

    ctx = DatasetContext()

    ctx.load()

    print("=" * 60)
    print("DATASET CONTEXT")
    print("=" * 60)

    print("Candles      :", len(ctx.candles))
    print("Gap Sessions :", len(ctx.gap_session))
    print("ORB Sessions :", len(ctx.orb_session))

    first = sorted(ctx.gap_session.keys())[0]

    print()
    print("First Day :", first)

    print("Gap :", ctx.gap_session[first])

    print("ORB :", ctx.orb_session[first])

    print("=" * 60)

    ctx.close()
