class SLTargetEngine:

    def __init__(self):

        self.min_confidence = 75

    def build(self,
              signal,
              confidence,
              spot,
              atr,
              strike):

        if confidence < self.min_confidence:

            return {

                "trade": False,

                "reason": "LOW_CONFIDENCE"

            }

        if signal == "BUY CE":

            sl = round(

                spot - (atr * 0.45),

                2

            )

            t1 = round(

                spot + (atr * 0.80),

                2

            )

            t2 = round(

                spot + (atr * 1.50),

                2

            )

        elif signal == "BUY PE":

            sl = round(

                spot + (atr * 0.45),

                2

            )

            t1 = round(

                spot - (atr * 0.80),

                2

            )

            t2 = round(

                spot - (atr * 1.50),

                2

            )

        else:

            return {

                "trade": False,

                "reason": "WAIT"

            }

        rr = round(

            abs(t2 - spot)

            /

            abs(spot - sl),

            2

        )

        return {

            "trade": True,

            "signal": signal,

            "strike": strike,

            "entry": round(spot, 2),

            "stop_loss": sl,

            "target1": t1,

            "target2": t2,

            "risk_reward": rr,

            "confidence": confidence

        }


if __name__ == "__main__":

    engine = SLTargetEngine()

    result = engine.build(

        signal="BUY CE",

        confidence=84,

        spot=77593.11,

        atr=55.39,

        strike="77600 CE"

    )

    print("=" * 60)

    print("SL TARGET ENGINE")

    print("=" * 60)

    for k, v in result.items():

        print(f"{k:15} : {v}")

    print("=" * 60)
