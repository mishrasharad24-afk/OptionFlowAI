from datetime import datetime

from live_market_reader import LiveMarketReader
from live_feature_builder import LiveFeatureBuilder
from market_memory_v3 import MarketMemoryV3

from gap_session_builder import GapSessionBuilder
from orb_session_builder import ORBSessionBuilder


class LiveAIEngine:

    def __init__(self):

        self.reader = LiveMarketReader()

        self.builder = LiveFeatureBuilder()

        self.memory = MarketMemoryV3()

    def analyse(self):

        candles = self.reader.latest_candles(limit=100)

        if len(candles) < 50:

            return {

                "signal": "WAIT",

                "reason": "NOT_ENOUGH_DATA"

            }

        gap = GapSessionBuilder()

        gap.load(candles)

        gap_session = gap.build()

        orb = ORBSessionBuilder()

        orb.load(candles)

        orb_session = orb.build()

        day = datetime.fromisoformat(

            candles[-1]["timestamp"]

        ).date()

        feature_row = self.builder.build(

            candles,

            gap_session,

            orb_session,

            day

        )

        if feature_row is None:

            return {

                "signal": "WAIT",

                "reason": "FEATURE_BUILD_FAILED"

            }

        result = self.memory.analyse(

            feature_row

        )

        return result


if __name__ == "__main__":

    app = LiveAIEngine()

    result = app.analyse()

    print("=" * 60)

    print("LIVE AI ENGINE")

    print("=" * 60)

    print("Signal      :", result["signal"])

    print("Reason      :", result["reason"])

    print("Bull Rate   :", result["bull_rate"], "%")

    print("Bear Rate   :", result["bear_rate"], "%")

    print("Confidence  :", result["confidence"], "%")

    print("Matches     :", result["matches"])

    print("=" * 60)

    app.reader.close()
