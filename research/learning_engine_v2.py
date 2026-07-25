import csv
from collections import defaultdict


class LearningEngineV2:

    def __init__(self):

        self.rows = []

        self.patterns = defaultdict(
            lambda: {
                "count": 0,
                "bull": 0,
                "bear": 0,
                "side": 0
            }
        )

    def load(self, filename="training_dataset.csv"):

        with open(filename, "r") as f:

            reader = csv.DictReader(f)

            for row in reader:

                row["gap_pct"] = float(row["gap_pct"])
                row["first_body_pct"] = float(row["first_body_pct"])
                row["first_range"] = float(row["first_range"])
                row["orb_range"] = float(row["orb_range"])
                row["day_range"] = float(row["day_range"])

                self.rows.append(row)

        print("Rows Loaded :", len(self.rows))

    def make_pattern(self, row):

        gap = "GAPUP" if row["gap_pct"] > 0 else "GAPDOWN"

        body = "STRONG" if row["first_body_pct"] >= 60 else "WEAK"

        first = "BULL" if row["bull_first"] == "1" else "BEAR"

        pdh = row["pdh_break"]

        pdl = row["pdl_break"]

        return (
            gap,
            body,
            first,
            pdh,
            pdl
        )

    def learn(self):

        for row in self.rows:

            pattern = self.make_pattern(row)

            self.patterns[pattern]["count"] += 1

            if row["day_result"] == "BULL":

                self.patterns[pattern]["bull"] += 1

            elif row["day_result"] == "BEAR":

                self.patterns[pattern]["bear"] += 1

            else:

                self.patterns[pattern]["side"] += 1


if __name__ == "__main__":

    ai = LearningEngineV2()

    ai.load()

    ai.learn()

    print("Patterns Learned :", len(ai.patterns))
