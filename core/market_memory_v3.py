import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESEARCH_DIR = os.path.join(BASE_DIR, "research")
LEARNING_DIR = os.path.join(RESEARCH_DIR, "learning")

sys.path.insert(0, RESEARCH_DIR)
sys.path.insert(0, LEARNING_DIR)

from learning_engine_v3 import LearningEngineV3


class MarketMemoryV3:

    def __init__(self):

        self.ai = LearningEngineV3()

    def analyse(self, feature_row):

        result = self.ai.analyse(feature_row)

        return {

            "signal": result["signal"]["signal"],

            "reason": result["signal"]["reason"],

            "bull_rate": result["signal"]["bull_rate"],

            "bear_rate": result["signal"]["bear_rate"],

            "side_rate": result["signal"]["side_rate"],

            "confidence": result["signal"]["confidence"],

            "matches": len(result["matches"])

        }


if __name__ == "__main__":

    app = MarketMemoryV3()

    today = app.ai.similarity.dataset[-1]

    result = app.analyse(today)

    print("=" * 60)
    print("OPTIONFLOW AI")
    print("=" * 60)

    print(f"Signal      : {result['signal']}")
    print(f"Reason      : {result['reason']}")
    print(f"Bull Rate   : {result['bull_rate']} %")
    print(f"Bear Rate   : {result['bear_rate']} %")
    print(f"Side Rate   : {result['side_rate']} %")
    print(f"Confidence  : {result['confidence']} %")
    print(f"Top Matches : {result['matches']}")

    print("=" * 60)
