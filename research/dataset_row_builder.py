from builder_gap import GapBuilder
from builder_candle import CandleBuilder
from builder_orb import ORBBuilder
from builder_ema import EMABuilder
from builder_vwap import VWAPBuilder
from builder_volume import VolumeBuilder


class DatasetRowBuilder:

    @staticmethod
    def build(
        today_open,
        previous_close,

        open_price,
        high,
        low,
        close,

        orb_high,
        orb_low,
        current_price,
        session_high,
        session_low,
        close_price,

        price,
        ema20,
        ema50,

        vwap,

        volume,
        average_volume
    ):

        row = {}

        row.update(
            GapBuilder.build(
                today_open,
                previous_close
            )
        )

        row.update(
            CandleBuilder.build(
                open_price,
                high,
                low,
                close
            )
        )

        row.update(
            ORBBuilder.build(
                orb_high,
                orb_low,
                current_price,
                session_high,
                session_low,
                close_price
            )
        )

        row.update(
            EMABuilder.build(
                price,
                ema20,
                ema50
            )
        )

        row.update(
            VWAPBuilder.build(
                price,
                vwap
            )
        )

        row.update(
            VolumeBuilder.build(
                volume,
                average_volume
            )
        )

        return row


if __name__ == "__main__":

    row = DatasetRowBuilder.build(

        today_open=25180,
        previous_close=25050,

        open_price=25100,
        high=25220,
        low=25080,
        close=25200,

        orb_high=25180,
        orb_low=25070,
        current_price=25210,
        session_high=25235,
        session_low=25090,
        close_price=25200,

        price=25220,
        ema20=25170,
        ema50=25110,

        vwap=25185,

        volume=245000,
        average_volume=180000

    )

    print("=" * 60)
    print("DATASET ROW BUILDER")
    print("=" * 60)

    for k, v in row.items():

        print(f"{k:22} : {v}")

    print("=" * 60)
