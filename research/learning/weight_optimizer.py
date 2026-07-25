from feature_statistics_v2 import FeatureStatisticsV2
from dataset_loader import DatasetLoader


class WeightOptimizer:

    def __init__(self):

        self.weights = {}

    def optimize(self, stats):

        for group in stats:

            self.weights[group] = {}

            for feature, item in stats[group].items():

                total = item["count"]

                if total == 0:

                    weight = 0.0

                else:

                    bull = item["bull"]

                    bear = item["bear"]

                    side = item["side"]

                    # Historical probability
                    bull_rate = bull / total
                    bear_rate = bear / total
                    side_rate = side / total

                    # Weight = strongest probability
                    weight = max(
                        bull_rate,
                        bear_rate,
                        side_rate
                    )

                self.weights[group][feature] = {

                    "weight": round(weight, 4),

                    "bull_rate": round(bull_rate, 4) if total else 0,

                    "bear_rate": round(bear_rate, 4) if total else 0,

                    "side_rate": round(side_rate, 4) if total else 0,

                    "count": total

                }

        return self.weights


if __name__ == "__main__":

    loader = DatasetLoader(
        "training_dataset_v3.csv"
    )

    rows = loader.load()

    stats = FeatureStatisticsV2().analyse(rows)

    optimizer = WeightOptimizer()

    weights = optimizer.optimize(stats)

    print("=" * 60)
    print("WEIGHT OPTIMIZER")
    print("=" * 60)

    for group in weights:

        print()

        print(group.upper())

        print("-" * 50)

        for feature, value in weights[group].items():

            print(
                f"{feature:15}"
                f" Weight={value['weight']:.2f}"
                f" Bull={value['bull_rate']:.2f}"
                f" Bear={value['bear_rate']:.2f}"
                f" Side={value['side_rate']:.2f}"
            )

    print("=" * 60)
