class ATRCalculator:

    @staticmethod
    def true_range(high, low, previous_close):

        tr1 = high - low
        tr2 = abs(high - previous_close)
        tr3 = abs(low - previous_close)

        return max(tr1, tr2, tr3)

    @staticmethod
    def calculate(highs, lows, closes, period=14):

        if len(closes) < period + 1:
            return None

        trs = []

        for i in range(1, len(closes)):

            tr = ATRCalculator.true_range(
                highs[i],
                lows[i],
                closes[i - 1]
            )

            trs.append(tr)

        if len(trs) < period:
            return None

        atr = sum(trs[-period:]) / period

        return round(atr, 2)


if __name__ == "__main__":

    highs = [
        101,102,103,104,105,106,107,
        108,109,110,111,112,113,114,115
    ]

    lows = [
        99,100,101,102,103,104,105,
        106,107,108,109,110,111,112,113
    ]

    closes = [
        100,101,102,103,104,105,106,
        107,108,109,110,111,112,113,114
    ]

    atr = ATRCalculator.calculate(
        highs,
        lows,
        closes
    )

    print("=" * 50)
    print("ATR CALCULATOR")
    print("=" * 50)
    print("ATR :", atr)
    print("=" * 50)
