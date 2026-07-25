from similarity_engine import SimilarityEngine


class ConfidenceEngine:

    def __init__(self):

        self.engine = SimilarityEngine()

        self.engine.load()

    def calculate(self, today, top=20):

        matches = self.engine.top_matches(today, top)

        bull = 0
        bear = 0
        side = 0

        for similarity, row in matches:

            trend = row["trend"]

            if trend == "BULL":
                bull += similarity

            elif trend == "BEAR":
                bear += similarity

            else:
                side += similarity

        total = bull + bear + side

        if total == 0:

            return {

                "bull_rate": 0.0,
                "bear_rate": 0.0,
                "side_rate": 0.0,
                "confidence": 0.0

            }

        bull_rate = bull / total
        bear_rate = bear / total
        side_rate = side / total

        confidence = max(
            bull_rate,
            bear_rate,
            side_rate
        )

        return {

            "bull_rate": round(bull_rate * 100, 2),

            "bear_rate": round(bear_rate * 100, 2),

            "side_rate": round(side_rate * 100, 2),

            "confidence": round(confidence * 100, 2)

        }


if __name__ == "__main__":

    app = ConfidenceEngine()

    today = app.engine.dataset[-1]

    result = app.calculate(today)

    print("=" * 60)
    print("CONFIDENCE ENGINE")
    print("=" * 60)

    print("Bull Rate :", result["bull_rate"], "%")
    print("Bear Rate :", result["bear_rate"], "%")
    print("Side Rate :", result["side_rate"], "%")
    print("Confidence:", result["confidence"], "%")

    print("=" * 60)
