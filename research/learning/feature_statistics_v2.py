from collections import defaultdict

from dataset_loader import DatasetLoader


class FeatureStatisticsV2:

    def __init__(self):

        self.stats = defaultdict(
            lambda: defaultdict(
                lambda: {

                    "count": 0,

                    "bull": 0,

                    "bear": 0,

                    "side": 0,

                    "atr_sum": 0.0,

                    "gap_sum": 0.0

                }
            )
        )

    def update(self,
               group,
               feature,
               row):

        item = self.stats[group][feature]

        item["count"] += 1

        trend = row["trend"]

        if trend == "BULL":

            item["bull"] += 1

        elif trend == "BEAR":

            item["bear"] += 1

        else:

            item["side"] += 1

        try:

            item["atr_sum"] += float(row["atr"])

        except:

            pass

        try:

            item["gap_sum"] += abs(

                float(row["gap_pct"])

            )

        except:

            pass

    def analyse(self, rows):

        for row in rows:

            self.update(
                "gap",
                row["gap_type"],
                row
            )

            self.update(
                "orb",
                row["orb_break"],
                row
            )

            self.update(
                "trend",
                row["trend"],
                row
            )

            self.update(
                "pdh",
                row["pdh_status"],
                row
            )

        return self.stats


if __name__ == "__main__":

    loader = DatasetLoader(

        "training_dataset_v3.csv"

    )

    rows = loader.load()

    engine = FeatureStatisticsV2()

    stats = engine.analyse(rows)

    print("=" * 60)

    print("FEATURE STATISTICS V2")

    print("=" * 60)

    for group in stats:

        print()

        print(group.upper())

        print("-" * 40)

        for name, item in stats[group].items():

            atr = 0

            gap = 0

            if item["count"] > 0:

                atr = round(

                    item["atr_sum"]

                    / item["count"],

                    2

                )

                gap = round(

                    item["gap_sum"]

                    / item["count"],

                    2

                )

            print(

                f"{name:15}"

                f" Count={item['count']}"

                f" Bull={item['bull']}"

                f" Bear={item['bear']}"

                f" ATR={atr}"

                f" Gap={gap}"

            )

    print("=" * 60)
