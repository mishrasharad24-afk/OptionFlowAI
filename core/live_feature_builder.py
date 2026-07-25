import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(BASE_DIR, "research"))

from indicator_builder import IndicatorBuilder
from feature_row_builder_v2 import FeatureRowBuilderV2


class LiveFeatureBuilder:

    def build(self,
              candles,
              gap_session,
              orb_session,
              day):

        if len(candles) < 50:

            return None

        return FeatureRowBuilderV2.build(

            candles,

            gap_session,

            orb_session,

            day

        )


if __name__ == "__main__":

    from live_market_reader import LiveMarketReader

    from gap_session_builder import GapSessionBuilder

    from orb_session_builder import ORBSessionBuilder

    from datetime import datetime

    reader = LiveMarketReader()

    candles = reader.latest_candles(

        limit=100

    )

    gap = GapSessionBuilder()

    gap.load(candles)

    gap_session = gap.build()

    orb = ORBSessionBuilder()

    orb.load(candles)

    orb_session = orb.build()

    day = datetime.fromisoformat(

        candles[-1]["timestamp"]

    ).date()

    builder = LiveFeatureBuilder()

    row = builder.build(

        candles,

        gap_session,

        orb_session,

        day

    )

    print("=" * 60)

    print("LIVE FEATURE BUILDER")

    print("=" * 60)

    if row:

        for k, v in row.items():

            print(f"{k:20} : {v}")

    else:

        print("Not Enough Candles")

    print("=" * 60)

    reader.close()
