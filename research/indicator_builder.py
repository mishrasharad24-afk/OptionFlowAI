from ema_calculator import EMACalculator
from atr_calculator import ATRCalculator
from pdh_pdl_calculator import PDHPDLCalculator


class IndicatorBuilder:

    @staticmethod
    def build(highs, lows, closes):

        if len(closes) < 50:
            return None

        ema20 = EMACalculator.calculate20(closes)
        ema50 = EMACalculator.calculate50(closes)

        atr = ATRCalculator.calculate(
            highs,
            lows,
            closes
        )

        pd = PDHPDLCalculator.summary(
            highs,
            lows,
            closes[-1]
        )

        trend = "SIDE"

        if ema20 and ema50:

            if ema20 > ema50:
                trend = "BULL"

            elif ema20 < ema50:
                trend = "BEAR"

        return {

            "ema20": ema20,

            "ema50": ema50,

            "atr": atr,

            "trend": trend,

            "pdh": pd["pdh"],

            "pdl": pd["pdl"],

            "pdh_status": pd["status"]

        }


if __name__ == "__main__":

    highs = []
    lows = []
    closes = []

    for i in range(60):

        highs.append(100 + i + 2)
        lows.append(100 + i - 2)
        closes.append(100 + i)

    row = IndicatorBuilder.build(
        highs,
        lows,
        closes
    )

    print("=" * 60)
    print("INDICATOR BUILDER")
    print("=" * 60)

    for k, v in row.items():

        print(f"{k:15} : {v}")

    print("=" * 60)
