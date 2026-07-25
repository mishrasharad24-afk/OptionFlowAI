class OpeningScore:

    def __init__(self):
        self.reset()

    def reset(self):

        self.bull = 0
        self.bear = 0
        self.reasons = []

    def calculate(self,
                  first,
                  second,
                  third,
                  previous_high,
                  previous_low):

        self.reset()

        # -------- First Candle --------

        if first["close"] > first["open"]:

            self.bull += 20
            self.reasons.append("Bull First Candle")

        else:

            self.bear += 20
            self.reasons.append("Bear First Candle")

        # -------- Body Strength --------

        rng = first["high"] - first["low"]

        if rng > 0:

            body = abs(first["close"] - first["open"])

            body_percent = body * 100 / rng

            if body_percent >= 60:

                if first["close"] > first["open"]:

                    self.bull += 15

                else:

                    self.bear += 15

                self.reasons.append("Strong Body")

        # -------- ORB --------

        orb_high = max(
            first["high"],
            second["high"],
            third["high"]
        )

        orb_low = min(
            first["low"],
            second["low"],
            third["low"]
        )

        if third["close"] > orb_high:

            self.bull += 20
            self.reasons.append("ORB Break Up")

        elif third["close"] < orb_low:

            self.bear += 20
            self.reasons.append("ORB Break Down")

        # -------- Previous Day --------

        if third["close"] > previous_high:

            self.bull += 20
            self.reasons.append("PDH Break")

        if third["close"] < previous_low:

            self.bear += 20
            self.reasons.append("PDL Break")

        confidence = max(self.bull, self.bear)

        if self.bull > self.bear:

            decision = "BUY CE"

        elif self.bear > self.bull:

            decision = "BUY PE"

        else:

            decision = "WAIT"

        return {

            "bull": self.bull,
            "bear": self.bear,
            "confidence": confidence,
            "decision": decision,
            "reasons": self.reasons
        }
