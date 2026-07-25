from indicator_builder import IndicatorBuilder
from dataset_row_builder import DatasetRowBuilder


class FeatureRowBuilderV2:

    @staticmethod
    def build(
        candles,
        gap_session,
        orb_session,
        day
    ):

        if len(candles) < 50:
            return None

        closes = [x["close"] for x in candles]
        highs = [x["high"] for x in candles]
        lows = [x["low"] for x in candles]
        opens = [x["open"] for x in candles]

        indicators = IndicatorBuilder.build(
            highs,
            lows,
            closes
        )

        gap = gap_session[day]
        orb = orb_session[day]

        row = DatasetRowBuilder.build(

            today_open=gap["open"],

            previous_close=gap["previous_close"],

            open_price=opens[-1],

            high=highs[-1],

            low=lows[-1],

            close=closes[-1],

            orb_high=orb["orb_high"],

            orb_low=orb["orb_low"],

            current_price=closes[-1],

            session_high=highs[-1],

            session_low=lows[-1],

            close_price=closes[-1],

            price=closes[-1],

            ema20=indicators["ema20"],

            ema50=indicators["ema50"],

            vwap=closes[-1],

            volume=0,

            average_volume=1

        )

        row.update(indicators)

        return row


if __name__ == "__main__":

    print("=" * 60)
    print("FEATURE ROW BUILDER V2 READY")
    print("=" * 60)
