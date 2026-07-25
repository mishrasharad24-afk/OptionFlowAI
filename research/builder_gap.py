from gap_features import GapFeatures


class GapBuilder:

    @staticmethod
    def build(today_open, previous_close):

        info = GapFeatures.summary(
            today_open,
            previous_close
        )

        return {

            "gap_pct": info["gap_pct"],

            "gap_type": info["gap_type"],

            "gap_strength": info["gap_strength"],

            "gap_bias": info["gap_bias"]

        }


if __name__ == "__main__":

    row = GapBuilder.build(

        today_open=25180,

        previous_close=25050

    )

    print("="*50)
    print("GAP BUILDER")
    print("="*50)

    for k,v in row.items():

        print(f"{k:15} : {v}")
