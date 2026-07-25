from vwap_features import VWAPFeatures


class VWAPBuilder:

    @staticmethod
    def build(price, vwap):

        side = VWAPFeatures.side(
            price,
            vwap
        )

        return {

            "vwap": round(vwap, 2),

            "vwap_side": side,

            "vwap_score":
                1 if side == "ABOVE"
                else -1 if side == "BELOW"
                else 0

        }


if __name__ == "__main__":

    row = VWAPBuilder.build(

        price=25220,

        vwap=25185

    )

    print("=" * 50)
    print("VWAP BUILDER")
    print("=" * 50)

    for k, v in row.items():

        print(f"{k:18} : {v}")

    print("=" * 50)
