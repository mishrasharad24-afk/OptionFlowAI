import math


class CandleFeatures:

    @staticmethod
    def body_percent(open_price, high, low, close):

        rng = high - low

        if rng <= 0:
            return 0.0

        body = abs(close - open_price)

        return round((body / rng) * 100, 2)

    @staticmethod
    def upper_wick_percent(open_price, high, low, close):

        rng = high - low

        if rng <= 0:
            return 0.0

        upper = high - max(open_price, close)

        return round((upper / rng) * 100, 2)

    @staticmethod
    def lower_wick_percent(open_price, high, low, close):

        rng = high - low

        if rng <= 0:
            return 0.0

        lower = min(open_price, close) - low

        return round((lower / rng) * 100, 2)

    @staticmethod
    def opening_strength(open_price, high, low, close):

        body = CandleFeatures.body_percent(
            open_price,
            high,
            low,
            close
        )

        if body >= 80:
            return "VERY_STRONG"

        if body >= 60:
            return "STRONG"

        if body >= 40:
            return "NORMAL"

        return "WEAK"
