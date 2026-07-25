from collections import defaultdict

from dataset_loader import DatasetLoader
from pattern_classifier import PatternClassifier


class FeatureStatistics:

    def __init__(self):

        self.stats = defaultdict(
            lambda: defaultdict(int)
        )

    def analyse(self, rows):

        for row in rows:

            pattern = PatternClassifier.classify(row)

            self.stats["pattern"][pattern] += 1

            self.stats["trend"][row["trend"]] += 1

            self.stats["gap"][row["gap_type"]] += 1

            self.stats["orb"][row["orb_break"]] += 1

            self.stats["pdh"][row["pdh_status"]] += 1

        return self.stats


if __name__ == "__main__":

    loader = DatasetLoader(
        "training_dataset_v2.csv"
    )

    rows = loader.load()

    engine = FeatureStatistics()

    stats = engine.analyse(rows)

    print("=" * 60)

    print("FEATURE STATISTICS")

    print("=" * 60)

    print()

    for group in stats:

        print(group.upper())

        for k, v in stats[group].items():

            print(f"{k:20} : {v}")

        print()

    print("=" * 60)
