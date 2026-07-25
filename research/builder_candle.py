from candle_features import CandleFeatures


class CandleBuilder:

    @staticmethod
    def build(open_price, high, low, close):

        return {

            "body_pct":
                CandleFeatures.body_percent(
                    open_price,
                    high,
                    low,
                    close
                ),

            "upper_wick_pct":
                CandleFeatures.upper_wick_percent(
                    open_price,
                    high,
                    low,
                    close
                ),

            "lower_wick_pct":
                CandleFeatures.lower_wick_percent(
                    open_price,
                    high,
                    low,
                    close
                ),

            "opening_strength":
                CandleFeatures.opening_strength(
                    open_price,
                    high,
                    low,
                    close
                )

        }


if __name__ == "__main__":

    row = CandleBuilder.build(

        open_price=25100,

        high=25220,

        low=25080,

        close=25200

    )

    print("=" * 50)
    print("CANDLE BUILDER")
    print("=" * 50)

    for k, v in row.items():

        print(f"{k:20} : {v}")

    print("=" * 50)
