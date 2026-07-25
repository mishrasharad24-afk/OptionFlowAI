from confidence_engine import ConfidenceEngine


class SignalEngine:

    def __init__(self):

        self.engine = ConfidenceEngine()

    def decide(self, today):

        result = self.engine.calculate(today)

        bull = result["bull_rate"]

        bear = result["bear_rate"]

        side = result["side_rate"]

        confidence = result["confidence"]

        signal = "WAIT"

        reason = "LOW_CONFIDENCE"

        if confidence >= 75:

            if bull > bear:

                signal = "BUY CE"

                reason = "BULLISH"

            elif bear > bull:

                signal = "BUY PE"

                reason = "BEARISH"

            else:

                signal = "WAIT"

                reason = "BALANCED"

        return {

            "signal": signal,

            "reason": reason,

            "bull_rate": bull,

            "bear_rate": bear,

            "side_rate": side,

            "confidence": confidence

        }


if __name__ == "__main__":

    app = SignalEngine()

    today = app.engine.engine.dataset[-1]

    result = app.decide(today)

    print("=" * 60)
    print("SIGNAL ENGINE")
    print("=" * 60)

    print("Signal      :", result["signal"])
    print("Reason      :", result["reason"])
    print("Bull Rate   :", result["bull_rate"], "%")
    print("Bear Rate   :", result["bear_rate"], "%")
    print("Side Rate   :", result["side_rate"], "%")
    print("Confidence  :", result["confidence"], "%")

    print("=" * 60)
