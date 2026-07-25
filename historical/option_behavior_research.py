import sys
import os
import csv
from datetime import datetime

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY

from historical.backtest_30day_chunk_base import (
    fetch,
    candle_map,
    load_contracts,
    find_contract
)

from historical.market_research_engine import (
    get_day_candles,
    classify_day,
    determine_regime
)


TOKEN_FILE = (
    "/home/ec2-user/OptionFlowAI/"
    "access_token.txt"
)

CONFIG = {
    "NIFTY": {
        "spot_segment": "NSE",
        "spot_token": "26000",
        "option_segment": "NFO",
        "strike_gap": 50
    },

    "SENSEX": {
        "spot_segment": "BSE",
        "spot_token": "51",
        "option_segment": "BFO",
        "strike_gap": 100
    }
}


RESEARCH_TIMES = [
    "09:20",
    "09:25",
    "09:30",
    "09:45",
    "10:15"
]


def analyse_option_snapshot(
    contracts,
    cache,
    m,
    cfg,
    day,
    expiry,
    atm,
    current_time,
    previous_time
):

    strikes = [
        atm + n * cfg["strike_gap"]
        for n in range(-2, 3)
    ]

    ce_up = 0
    ce_down = 0

    pe_up = 0
    pe_down = 0

    ce_vol_up = 0
    pe_vol_up = 0

    valid = 0

    ce_momentum_total = 0
    pe_momentum_total = 0

    for strike in strikes:

        ce = find_contract(
            contracts,
            expiry,
            strike,
            "CE"
        )

        pe = find_contract(
            contracts,
            expiry,
            strike,
            "PE"
        )

        if not ce or not pe:
            continue

        for opt in (ce, pe):

            token = opt["token"]

            if token not in cache:

                try:

                    cache[token] = fetch(
                        m,
                        cfg["option_segment"],
                        token
                    )

                except Exception:

                    cache[token] = []

        cem = candle_map(
            cache[ce["token"]],
            day
        )

        pem = candle_map(
            cache[pe["token"]],
            day
        )

        if (
            current_time not in cem
            or previous_time not in cem
            or current_time not in pem
            or previous_time not in pem
        ):
            continue

        ce_now = cem[current_time]
        ce_prev = cem[previous_time]

        pe_now = pem[current_time]
        pe_prev = pem[previous_time]

        ce_momentum = (
            float(ce_now[4])
            - float(ce_prev[4])
        )

        pe_momentum = (
            float(pe_now[4])
            - float(pe_prev[4])
        )

        ce_momentum_total += (
            ce_momentum
        )

        pe_momentum_total += (
            pe_momentum
        )

        if ce_momentum > 0:
            ce_up += 1

        elif ce_momentum < 0:
            ce_down += 1

        if pe_momentum > 0:
            pe_up += 1

        elif pe_momentum < 0:
            pe_down += 1

        if (
            float(ce_now[5])
            > float(ce_prev[5])
        ):
            ce_vol_up += 1

        if (
            float(pe_now[5])
            > float(pe_prev[5])
        ):
            pe_vol_up += 1

        valid += 1

    if valid == 0:
        return None

    if (
        ce_up >= 4
        and pe_down >= 4
    ):
        bias = "CE_STRONG"

    elif (
        pe_up >= 4
        and ce_down >= 4
    ):
        bias = "PE_STRONG"

    elif ce_up > pe_up:
        bias = "CE_LEAN"

    elif pe_up > ce_up:
        bias = "PE_LEAN"

    else:
        bias = "MIXED"

    return {
        "valid": valid,
        "ce_up": ce_up,
        "ce_down": ce_down,
        "pe_up": pe_up,
        "pe_down": pe_down,
        "ce_vol": ce_vol_up,
        "pe_vol": pe_vol_up,
        "ce_momentum": ce_momentum_total,
        "pe_momentum": pe_momentum_total,
        "bias": bias
    }
def research_index(
    m,
    index
):

    cfg = CONFIG[index]

    print(
        "\n"
        + "=" * 110
    )

    print(
        "OPTION BEHAVIOR RESEARCH:",
        index
    )

    spot_all = fetch(
        m,
        cfg["spot_segment"],
        cfg["spot_token"]
    )

    if not spot_all:

        print("NO SPOT DATA")
        return

    days = sorted({
        x[0][:10]
        for x in spot_all
    })

    contracts = load_contracts(
        index
    )

    cache = {}

    previous_close = None

    for day in days:

        rows = get_day_candles(
            spot_all,
            day
        )

        if not rows:
            continue

        market_data = classify_day(
            rows,
            previous_close
        )

        regime = determine_regime(
            market_data
        )

        day_date = datetime.strptime(
            day,
            "%Y-%m-%d"
        ).date()

        expiries = sorted({
            x["expiry"]
            for x in contracts
            if x["expiry"] >= day_date
        })

        if not expiries:

            print(
                day,
                "|",
                regime,
                "| NO EXPIRY"
            )

            previous_close = (
                market_data["close"]
            )

            continue

        expiry = expiries[0]

        smap = candle_map(
            spot_all,
            day
        )

        print(
            "\n"
            f"{day} | "
            f"{regime} | "
            f"EXPIRY {expiry}"
        )

        for current_time in (
            RESEARCH_TIMES
        ):

            if current_time not in smap:
                continue

            times_before = sorted(
                t for t in smap
                if t < current_time
            )

            if not times_before:
                continue

            previous_time = (
                times_before[-1]
            )

            spot = float(
                smap[current_time][4]
            )

            atm = int(
                round(
                    spot
                    / cfg["strike_gap"]
                )
                * cfg["strike_gap"]
            )

            snapshot = (
                analyse_option_snapshot(
                    contracts,
                    cache,
                    m,
                    cfg,
                    day,
                    expiry,
                    atm,
                    current_time,
                    previous_time
                )
            )

            if not snapshot:

                print(
                    f"  {current_time} | "
                    f"ATM {atm} | "
                    f"NO OPTION DATA"
                )

                continue

            print(
                f"  {current_time} | "
                f"ATM {atm} | "
                f"CE UP "
                f"{snapshot['ce_up']}/"
                f"{snapshot['valid']} | "
                f"PE DOWN "
                f"{snapshot['pe_down']}/"
                f"{snapshot['valid']} | "
                f"PE UP "
                f"{snapshot['pe_up']}/"
                f"{snapshot['valid']} | "
                f"CE DOWN "
                f"{snapshot['ce_down']}/"
                f"{snapshot['valid']} | "
                f"CE VOL "
                f"{snapshot['ce_vol']}/"
                f"{snapshot['valid']} | "
                f"PE VOL "
                f"{snapshot['pe_vol']}/"
                f"{snapshot['valid']} | "
                f"CE MOM "
                f"{snapshot['ce_momentum']:+.2f} | "
                f"PE MOM "
                f"{snapshot['pe_momentum']:+.2f} | "
                f"{snapshot['bias']}"
            )

        previous_close = (
            market_data["close"]
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
