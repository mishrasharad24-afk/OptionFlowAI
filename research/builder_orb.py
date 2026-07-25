from orb_features import ORBFeatures


class ORBBuilder:

    @staticmethod
    def build(
        orb_high,
        orb_low,
        current_price,
        session_high,
        session_low,
        close_price
    ):

        info = ORBFeatures.summary(
            orb_high,
            orb_low,
            current_price,
            session_high,
            session_low,
            close_price
        )

        return {

            "orb_high": info["orb_high"],

            "orb_low": info["orb_low"],

            "orb_range": info["orb_range"],

            "orb_strength": info["orb_strength"],

            "orb_break": info["orb_break"],

            "orb_hold": info["orb_hold"],

            "fake_breakout": info["fake_breakout"]

        }


if __name__ == "__main__":

    row = ORBBuilder.build(

        orb_high=25180,

        orb_low=25070,

        current_price=25210,

        session_high=25235,

        session_low=25090,

        close_price=25200

    )

    print("=" * 50)
    print("ORB BUILDER")
    print("=" * 50)

    for k, v in row.items():

        print(f"{k:20} : {v}")

    print("=" * 50)
