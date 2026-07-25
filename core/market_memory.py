import csv


class MarketMemory:

    def __init__(self):
        self.data = []

    def load(self, filename):

        with open(filename, "r", newline="") as f:

            reader = csv.DictReader(f)

            for row in reader:

                self.data.append({
                    "date": row["date"],
                    "gap": float(row["gap_pct"]),
                    "body": float(row["first_body_pct"]),
                    "range": float(row["first_range"]),
                    "orb": float(row["orb_range"]),
                    "bull": int(row["bull_first"]),
                    "bear": int(row["bear_first"]),
                    "pdh": int(row["pdh_break"]),
                    "pdl": int(row["pdl_break"]),
                    "result": row["day_result"]
                })

    def score(self, live, hist):

        s = 0.0

        s += abs(live["gap"] - hist["gap"]) * 2
        s += abs(live["body"] - hist["body"]) / 10
        s += abs(live["range"] - hist["range"]) / 20
        s += abs(live["orb"] - hist["orb"]) / 20

        if live["bull"] != hist["bull"]:
            s += 5

        if live["bear"] != hist["bear"]:
            s += 5

        if live["pdh"] != hist["pdh"]:
            s += 5

        if live["pdl"] != hist["pdl"]:
            s += 5

        return s

    def top_matches(self, live, top=5):

        rows = []

        for item in self.data:
            rows.append((self.score(live, item), item))

        rows.sort(key=lambda x: x[0])

        return rows[:top]

    def predict(self, live):

        matches = self.top_matches(live)

        bull = 0
        bear = 0
        side = 0

        for _, row in matches:

            if row["result"] == "BULL":
                bull += 1

            elif row["result"] == "BEAR":
                bear += 1

            else:
                side += 1

        total = len(matches)

        bull_rate = round(bull * 100 / total, 2)
        bear_rate = round(bear * 100 / total, 2)
        side_rate = round(side * 100 / total, 2)

        if bull_rate >= 80:
            signal = "BUY CE"
        elif bear_rate >= 80:
            signal = "BUY PE"
        else:
            signal = "NO TRADE"

        return signal, bull_rate, bear_rate, side_rate, matches


if __name__ == "__main__":

    ai = MarketMemory()

    ai.load("training_dataset.csv")

    live = {
        "gap": 0.40,
        "body": 70,
        "range": 120,
        "orb": 180,
        "bull": 1,
        "bear": 0,
        "pdh": 1,
        "pdl": 0
    }

    signal, bull, bear, side, matches = ai.predict(live)

    print("=" * 60)
    print("OPTIONFLOW AI")
    print("=" * 60)
    print("Signal      :", signal)
    print("Bull Rate   :", bull, "%")
    print("Bear Rate   :", bear, "%")
    print("Side Rate   :", side, "%")
    print("=" * 60)
    print("TOP 5 HISTORICAL MATCHES")
    print("=" * 60)

    for score, row in matches:

        similarity = max(0, round(100 - score, 2))

        print(
            row["date"],
            "|",
            row["result"],
            "| Similarity:",
            similarity,
            "%"
        )

    print("=" * 60)
