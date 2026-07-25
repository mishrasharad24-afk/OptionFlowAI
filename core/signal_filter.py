class SignalFilter:

    def __init__(self):

        self.min_confidence = 75.0
        self.min_matches = 10
        self.min_bull_gap = 10.0

    def evaluate(self, ai_result):

        reasons = []

        allow = True

        confidence = ai_result.get("confidence", 0)
        matches = ai_result.get("matches", 0)
        bull = ai_result.get("bull_rate", 0)
        bear = ai_result.get("bear_rate", 0)
        signal = ai_result.get("signal", "WAIT")

        if signal == "WAIT":

            allow = False
            reasons.append("WAIT_SIGNAL")

        if confidence < self.min_confidence:

            allow = False
            reasons.append("LOW_CONFIDENCE")

        if matches < self.min_matches:

            allow = False
            reasons.append("LOW_MATCHES")

        if signal == "BUY CE":

            if (bull - bear) < self.min_bull_gap:

                allow = False
                reasons.append("WEAK_BULL")

        elif signal == "BUY PE":

            if (bear - bull) < self.min_bull_gap:

                allow = False
                reasons.append("WEAK_BEAR")

        return {

            "allow_trade": allow,

            "signal": signal,

            "confidence": confidence,

            "matches": matches,

            "bull_rate": bull,

            "bear_rate": bear,

            "reasons": reasons

        }


if __name__ == "__main__":

    result = {

        "signal": "BUY CE",

        "confidence": 82.4,

        "matches": 20,

        "bull_rate": 82.4,

        "bear_rate": 13.6

    }

    engine = SignalFilter()

    out = engine.evaluate(result)

    print("=" * 60)
    print("SIGNAL FILTER")
    print("=" * 60)

    print("Allow Trade :", out["allow_trade"])
    print("Signal      :", out["signal"])
    print("Confidence  :", out["confidence"])
    print("Matches     :", out["matches"])
    print("Reasons     :", out["reasons"])

    print("=" * 60)
