class EMACalculator:

    @staticmethod
    def calculate(closes, period):

        if len(closes) < period:
            return None

        multiplier = 2 / (period + 1)

        ema = sum(closes[:period]) / period

        for price in closes[period:]:

            ema = (price - ema) * multiplier + ema

        return round(ema, 2)

    @staticmethod
    def calculate20(closes):

        return EMACalculator.calculate(
            closes,
            20
        )

    @staticmethod
    def calculate50(closes):

        return EMACalculator.calculate(
            closes,
            50
        )


if __name__ == "__main__":

    closes = []

    for i in range(100):

        closes.append(100 + i)

    ema20 = EMACalculator.calculate20(closes)

    ema50 = EMACalculator.calculate50(closes)

    print("=" * 50)
    print("EMA CALCULATOR")
    print("=" * 50)

    print("EMA20 :", ema20)

    print("EMA50 :", ema50)

    print("=" * 50)
