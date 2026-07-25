class PDHPDLCalculator:

    @staticmethod
    def previous_day(highs, lows):

        if len(highs) < 2 or len(lows) < 2:
            return None

        return {

            "pdh": highs[-2],

            "pdl": lows[-2]

        }

    @staticmethod
    def break_status(price, pdh, pdl):

        if price > pdh:
            return "PDH_BREAK"

        if price < pdl:
            return "PDL_BREAK"

        return "INSIDE"

    @staticmethod
    def summary(highs, lows, current_price):

        prev = PDHPDLCalculator.previous_day(
            highs,
            lows
        )

        if prev is None:
            return None

        return {

            "pdh": prev["pdh"],

            "pdl": prev["pdl"],

            "status": PDHPDLCalculator.break_status(

                current_price,

                prev["pdh"],

                prev["pdl"]

            )

        }


if __name__ == "__main__":

    highs = [

        74500,

        74820,

        75210,

        75480,

        75720

    ]

    lows = [

        73900,

        74210,

        74750,

        75020,

        75300

    ]

    row = PDHPDLCalculator.summary(

        highs,

        lows,

        current_price=75810

    )

    print("=" * 50)

    print("PDH / PDL CALCULATOR")

    print("=" * 50)

    for k, v in row.items():

        print(f"{k:10} : {v}")

    print("=" * 50)
