class GapFeatures:

    @staticmethod
    def gap_percent(today_open, previous_close):

        if previous_close <= 0:
            return 0.0

        return round(
            ((today_open - previous_close) / previous_close) * 100,
            2
        )

    @staticmethod
    def gap_type(gap):

        if gap >= 0.50:
            return "GAP_UP"

        if gap <= -0.50:
            return "GAP_DOWN"

        return "FLAT"

    @staticmethod
    def gap_strength(gap):

        value = abs(gap)

        if value >= 1.00:
            return "VERY_STRONG"

        if value >= 0.50:
            return "STRONG"

        if value >= 0.20:
            return "NORMAL"

        return "WEAK"

    @staticmethod
    def gap_bias(gap):

        if gap > 0:
            return "BULL"

        if gap < 0:
            return "BEAR"

        return "SIDE"

    @staticmethod
    def summary(today_open, previous_close):

        gap = GapFeatures.gap_percent(
            today_open,
            previous_close
        )

        return {
            "gap_pct": gap,
            "gap_type": GapFeatures.gap_type(gap),
            "gap_strength": GapFeatures.gap_strength(gap),
            "gap_bias": GapFeatures.gap_bias(gap)
        }


if __name__ == "__main__":

    result = GapFeatures.summary(
        today_open=25180,
        previous_close=25050
    )

    print("=" * 50)
    print("GAP FEATURE ENGINE")
    print("=" * 50)

    for k, v in result.items():
        print(f"{k:15} : {v}")

    print("=" * 50)
