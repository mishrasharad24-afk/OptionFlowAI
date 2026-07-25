import sys
import os
from datetime import datetime

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY
from historical.backtest_30day_chunk_base import fetch


TOKEN_FILE = (
    "/home/ec2-user/OptionFlowAI/"
    "access_token.txt"
)

CONFIG = {
    "NIFTY": {
        "segment": "NSE",
        "token": "26000"
    },
    "SENSEX": {
        "segment": "BSE",
        "token": "51"
    }
}


def get_day_candles(
    candles,
    day
):
    return [
        x for x in candles
        if x[0].startswith(day)
    ]


def get_close_at(
    rows,
    target_time
):
    for row in rows:

        time = row[0][11:16]

        if time == target_time:
            return float(row[4])

    return None


def classify_day(
    rows,
    prev_close
):

    if not rows:
        return None

    open_price = float(
        rows[0][1]
    )

    close_price = float(
        rows[-1][4]
    )

    day_high = max(
        float(x[2])
        for x in rows
    )

    day_low = min(
        float(x[3])
        for x in rows
    )

    close_15 = get_close_at(
        rows,
        "09:30"
    )

    close_30 = get_close_at(
        rows,
        "09:45"
    )

    close_60 = get_close_at(
        rows,
        "10:15"
    )

    if prev_close:

        gap_points = (
            open_price - prev_close
        )

        gap_pct = (
            gap_points /
            prev_close
        ) * 100

    else:

        gap_points = 0
        gap_pct = 0

    if gap_pct >= 0.15:

        gap_type = "GAP_UP"

    elif gap_pct <= -0.15:

        gap_type = "GAP_DOWN"

    else:

        gap_type = "FLAT_OPEN"

    gap_filled = False

    if prev_close:

        if (
            gap_type == "GAP_UP"
            and day_low <= prev_close
        ):
            gap_filled = True

        elif (
            gap_type == "GAP_DOWN"
            and day_high >= prev_close
        ):
            gap_filled = True

    move_15 = (
        close_15 - open_price
        if close_15 is not None
        else 0
    )

    move_30 = (
        close_30 - open_price
        if close_30 is not None
        else 0
    )

    move_60 = (
        close_60 - open_price
        if close_60 is not None
        else 0
    )

    day_move = (
        close_price - open_price
    )

    day_range = (
        day_high - day_low
    )

    return {
        "open": open_price,
        "prev_close": prev_close,
        "gap_points": gap_points,
        "gap_pct": gap_pct,
        "gap_type": gap_type,
        "gap_filled": gap_filled,
        "move_15": move_15,
        "move_30": move_30,
        "move_60": move_60,
        "day_move": day_move,
        "day_high": day_high,
        "day_low": day_low,
        "day_range": day_range,
        "close": close_price
    }
def determine_regime(data):

    gap_type = data["gap_type"]
    gap_filled = data["gap_filled"]

    move_30 = data["move_30"]
    move_60 = data["move_60"]
    day_move = data["day_move"]

    day_range = data["day_range"]

    if day_range > 0:

        strength = abs(
            day_move
        ) / day_range

    else:

        strength = 0

    # GAP UP scenarios
    if gap_type == "GAP_UP":

        if (
            not gap_filled
            and move_30 > 0
            and day_move > 0
        ):
            regime = "GAP_UP_TREND"

        elif (
            gap_filled
            and day_move < 0
        ):
            regime = "GAP_UP_REVERSAL"

        elif gap_filled:
            regime = "GAP_UP_GAP_FILL"

        else:
            regime = "GAP_UP_MIXED"

    # GAP DOWN scenarios
    elif gap_type == "GAP_DOWN":

        if (
            not gap_filled
            and move_30 < 0
            and day_move < 0
        ):
            regime = "GAP_DOWN_TREND"

        elif (
            gap_filled
            and day_move > 0
        ):
            regime = "GAP_DOWN_RECOVERY"

        elif gap_filled:
            regime = "GAP_DOWN_GAP_FILL"

        else:
            regime = "GAP_DOWN_MIXED"

    # FLAT OPEN scenarios
    else:

        if (
            move_30 > 0
            and move_60 > 0
            and day_move > 0
            and strength >= 0.30
        ):
            regime = "FLAT_BULL_TREND"

        elif (
            move_30 < 0
            and move_60 < 0
            and day_move < 0
            and strength >= 0.30
        ):
            regime = "FLAT_BEAR_TREND"

        elif strength < 0.20:
            regime = "SIDEWAYS"

        elif day_move > 0:
            regime = "FLAT_BULL_MIXED"

        elif day_move < 0:
            regime = "FLAT_BEAR_MIXED"

        else:
            regime = "SIDEWAYS"

    return regime


def research_index(
    m,
    index
):

    cfg = CONFIG[index]

    print(
        "\n"
        + "=" * 100
    )

    print(
        "HISTORICAL MARKET RESEARCH:",
        index
    )

    candles = fetch(
        m,
        cfg["segment"],
        cfg["token"]
    )

    if not candles:

        print(
            "NO HISTORICAL DATA"
        )

        return

    days = sorted({
        x[0][:10]
        for x in candles
    })

    regime_counts = {}

    previous_close = None

    for day in days:

        rows = get_day_candles(
            candles,
            day
        )

        if not rows:
            continue

        data = classify_day(
            rows,
            previous_close
        )

        regime = determine_regime(
            data
        )

        regime_counts[regime] = (
            regime_counts.get(
                regime,
                0
            ) + 1
        )

        gap_fill_text = (
            "YES"
            if data["gap_filled"]
            else "NO"
        )

        print(
            f"{day} | "
            f"{data['gap_type']} "
            f"{data['gap_pct']:+.2f}% | "
            f"15M {data['move_15']:+.2f} | "
            f"30M {data['move_30']:+.2f} | "
            f"60M {data['move_60']:+.2f} | "
            f"DAY {data['day_move']:+.2f} | "
            f"FILL {gap_fill_text} | "
            f"{regime}"
        )

        previous_close = data[
            "close"
        ]

    print(
        "\n"
        + "-" * 60
    )

    print(
        "REGIME SUMMARY:",
        index
    )

    print(
        "TRADING DAYS:",
        len(days)
    )

    for regime in sorted(
        regime_counts
    ):

        print(
            regime,
            ":",
            regime_counts[
                regime
            ]
        )


def main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token
    )

    for index in (
        "NIFTY",
        "SENSEX"
    ):

        try:

            research_index(
                m,
                index
            )

        except Exception as e:

            print(
                "ERROR",
                index,
                type(e).__name__,
                e
            )


if __name__ == "__main__":
    main()
