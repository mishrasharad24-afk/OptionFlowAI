class PatternClassifier:

    @staticmethod
    def classify(row):

        score = 0

        # Trend

        if row["trend"] == "BULL":
            score += 2

        elif row["trend"] == "BEAR":
            score -= 2

        # Gap

        if row["gap_type"] == "GAP_UP":
            score += 1

        elif row["gap_type"] == "GAP_DOWN":
            score -= 1

        # ORB

        if row["orb_break"] == "BREAK_UP":
            score += 2

        elif row["orb_break"] == "BREAK_DOWN":
            score -= 2

        # PDH / PDL

        if row["pdh_status"] == "PDH_BREAK":
            score += 2

        elif row["pdh_status"] == "PDL_BREAK":
            score -= 2

        # Decision

        if score >= 4:
            return "STRONG_BULL"

        if score >= 2:
            return "BULL"

        if score <= -4:
            return "STRONG_BEAR"

        if score <= -2:
            return "BEAR"

        return "SIDE"


if __name__ == "__main__":

    sample = {

        "trend": "BULL",

        "gap_type": "GAP_UP",

        "orb_break": "BREAK_UP",

        "pdh_status": "PDH_BREAK"

    }

    print("=" * 60)
    print("PATTERN CLASSIFIER")
    print("=" * 60)

    print("Pattern :", PatternClassifier.classify(sample))

    print("=" * 60)
