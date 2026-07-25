from feature_statistics_v2 import FeatureStatisticsV2
from weight_optimizer import WeightOptimizer
from similarity_engine import SimilarityEngine
from confidence_engine import ConfidenceEngine
from signal_engine import SignalEngine


class LearningEngineV3:

    def __init__(self):

        self.similarity = SimilarityEngine()

        self.similarity.load()

        self.confidence = ConfidenceEngine()

        self.signal = SignalEngine()

    def analyse(self, today):

        stats = FeatureStatisticsV2().analyse(
            self.similarity.dataset
        )

        weights = WeightOptimizer().optimize(
            stats
        )

        matches = self.similarity.top_matches(
            today,
            top=20
        )

        confidence = self.confidence.calculate(
            today
        )

        signal = self.signal.decide(
            today
        )

        return {

            "statistics": stats,

            "weights": weights,

            "matches": matches,

            "confidence": confidence,

            "signal": signal

        }


if __name__ == "__main__":

    engine = LearningEngineV3()

    today = engine.similarity.dataset[-1]

    result = engine.analyse(today)

    print("=" * 60)

    print("LEARNING ENGINE V3")

    print("=" * 60)

    print()

    print("Top Matches :",
          len(result["matches"]))

    print()

    print("Signal      :",
          result["signal"]["signal"])

    print("Reason      :",
          result["signal"]["reason"])

    print("Bull Rate   :",
          result["signal"]["bull_rate"], "%")

    print("Bear Rate   :",
          result["signal"]["bear_rate"], "%")

    print("Confidence  :",
          result["signal"]["confidence"], "%")

    print()

    print("Weight Groups :",
          len(result["weights"]))

    print("=" * 60)
