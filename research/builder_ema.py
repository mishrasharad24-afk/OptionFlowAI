from ema_features import EMAFeatures


class EMABuilder:

    @staticmethod
    def build(price, ema20, ema50):

        return {

            "ema20_side":
                EMAFeatures.side(
                    price,
                    ema20
                ),

            "ema50_side":
                EMAFeatures.side(
                    price,
                    ema50
                ),

            "ema_alignment":
                EMAFeatures.alignment(
                    ema20,
                    ema50
                )

        }


if __name__ == "__main__":

    row = EMABuilder.build(

        price=25220,

        ema20=25170,

        ema50=25110

    )

    print("=" * 50)
    print("EMA BUILDER")
    print("=" * 50)

    for k, v in row.items():

        print(f"{k:20} : {v}")

    print("=" * 50)
