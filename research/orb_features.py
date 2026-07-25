class ORBFeatures:

    @staticmethod
    def range(high, low):
        return round(high - low, 2)

    @staticmethod
    def breakout(high, low, price):

        if price > high:
            return "BREAK_UP"

        if price < low:
            return "BREAK_DOWN"

        return "INSIDE"

    @staticmethod
    def hold(high, low, close):

        if close >= high:
            return "HOLD_UP"

        if close <= low:
            return "HOLD_DOWN"

        return "FAILED"

    @staticmethod
    def fake_breakout(high, low, high_after, low_after, close):

        if high_after > high and close < high:
            return "FAKE_UP"

        if low_after < low and close > low:
            return "FAKE_DOWN"

        return "NO"

    @staticmethod
    def strength(high, low):

        r = high - low

        if r >= 150:
            return "WIDE"

        if r >= 80:
            return "NORMAL"

        return "NARROW"

    @staticmethod
    def summary(
        orb_high,
        orb_low,
        current_price,
        session_high,
        session_low,
        close_price
    ):

        return {

            "orb_high": orb_high,

            "orb_low": orb_low,

            "orb_range": ORBFeatures.range(
                orb_high,
                orb_low
            ),

            "orb_strength": ORBFeatures.strength(
                orb_high,
                orb_low
            ),

            "orb_break": ORBFeatures.breakout(
                orb_high,
                orb_low,
                current_price
            ),

            "orb_hold": ORBFeatures.hold(
                orb_high,
                orb_low,
                close_price
            ),

            "fake_breakout": ORBFeatures.fake_breakout(
                orb_high,
                orb_low,
                session_high,
                session_low,
                close_price
            )

        }


if __name__ == "__main__":

    result = ORBFeatures.summary(

        orb_high=25180,
        orb_low=25070,

        current_price=25210,

        session_high=25235,
        session_low=25090,

        close_price=25200

    )

    print("=" * 50)
    print("ORB FEATURE ENGINE")
    print("=" * 50)

    for k, v in result.items():
        print(f"{k:18} : {v}")

    print("=" * 50)
