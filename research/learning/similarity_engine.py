from dataset_loader import DatasetLoader
from weight_optimizer import WeightOptimizer
from feature_statistics_v2 import FeatureStatisticsV2


class SimilarityEngine:

    def __init__(self):

        self.dataset = []

        self.weights = {}

    def load(self):

        loader = DatasetLoader(
            "training_dataset_v3.csv"
        )

        self.dataset = loader.load()

        stats = FeatureStatisticsV2().analyse(
            self.dataset
        )

        self.weights = WeightOptimizer().optimize(
            stats
        )

    def similarity(self, today, historical):

        score = 0.0

        total = 0.0

        checks = [

            ("gap", "gap_type"),
            ("trend", "trend"),
            ("orb", "orb_break"),
            ("pdh", "pdh_status")

        ]

        for group, column in checks:

            feature = historical[column]

            weight = self.weights[group].get(
                feature,
                {"weight": 0.0}
            )["weight"]

            total += weight

            if today[column] == historical[column]:

                score += weight

        if total == 0:

            return 0

        return round(
            score / total,
            4
        )

    def top_matches(
            self,
            today,
            top=20
    ):

        result = []

        for row in self.dataset:

            sim = self.similarity(
                today,
                row
            )

            result.append(

                (

                    sim,

                    row

                )

            )

        result.sort(

            key=lambda x: x[0],

            reverse=True

        )

        return result[:top]


if __name__ == "__main__":

    engine = SimilarityEngine()

    engine.load()

    today = engine.dataset[-1]

    matches = engine.top_matches(today)

    print("=" * 60)
    print("SIMILARITY ENGINE")
    print("=" * 60)

    print("Top Matches :", len(matches))

    print()

    for sim, row in matches[:10]:

        print(

            row["timestamp"],

            row["symbol"],

            sim

        )

    print("=" * 60)
