import csv
from collections import defaultdict


patterns = defaultdict(lambda: {
    "count": 0,
    "bull": 0,
    "bear": 0,
    "side": 0
})


with open("training_dataset.csv", "r") as f:

    reader = csv.DictReader(f)

    for row in reader:

        pattern = (
            row["bull_first"],
            row["bear_first"],
            row["pdh_break"],
            row["pdl_break"]
        )

        patterns[pattern]["count"] += 1

        if row["day_result"] == "BULL":
            patterns[pattern]["bull"] += 1

        elif row["day_result"] == "BEAR":
            patterns[pattern]["bear"] += 1

        else:
            patterns[pattern]["side"] += 1


print("=" * 70)
print("LEARNING ENGINE")
print("=" * 70)

results = []

for pattern, stat in patterns.items():

    total = stat["count"]

    if total < 20:
        continue

    bull = stat["bull"]
    bear = stat["bear"]
    side = stat["side"]

    win = max(bull, bear)

    win_rate = round((win / total) * 100, 2)

    results.append(
        (
            win_rate,
            total,
            pattern,
            bull,
            bear,
            side
        )
    )

results.sort(reverse=True)

for win_rate, total, pattern, bull, bear, side in results:

    print()

    print("Pattern      :", pattern)
    print("Occurrences  :", total)
    print("Bull Days    :", bull)
    print("Bear Days    :", bear)
    print("Side Days    :", side)
    print("Win Rate     :", win_rate, "%")

print("=" * 70)
print("Patterns Found :", len(results))
print("=" * 70)
