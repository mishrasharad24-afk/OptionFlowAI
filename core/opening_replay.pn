import sys
import os
from datetime import datetime

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.market_data import MarketData
from core.option_market_data import OptionMarketData
from core.option_selector import (
    calculate_atm,
    load_option_contracts,
    INDEX_CONFIG
)


START_TIME = "09:15"
END_TIME = "09:25"
LOOKBACK = 3


def get_candles(data):
    return data.get("data", {}).get("candles") or []


def make_candle_map(candles):

    result = {}

    for candle in candles:

        try:
            dt = datetime.fromisoformat(candle[0])
        except Exception:
            continue

        t = dt.strftime("%H:%M")

        result[t] = {
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5])
        }

    return result


def find_contract(
    contracts,
    expiry,
    strike,
    option_type
):

    return next(
        (
            c for c in contracts
            if c["expiry"] == expiry
            and c["strike"] == strike
            and c["type"] == option_type
        ),
        None
    )


def get_same_contract_info(
    candle_map,
    current_time,
    all_times
):

    if current_time not in candle_map:
        return None

    current_index = all_times.index(
        current_time
    )

    available_times = all_times[
        :current_index + 1
    ]

    contract_times = [
        t for t in available_times
        if t in candle_map
    ]

    recent_times = contract_times[
        -LOOKBACK:
    ]

    if not recent_times:
        return None

    current = candle_map[
        current_time
    ]

    oldest = candle_map[
        recent_times[0]
    ]

    momentum = (
        current["close"]
        - oldest["close"]
    )

    # ------------------------------------------
    # VOLUME CONFIRMATION
    #
    # Current cumulative/returned volume is
    # compared with previous available candle.
    # ------------------------------------------

    volume_up = False

    if len(recent_times) >= 2:

        previous_time = recent_times[-2]

        previous_volume = candle_map[
            previous_time
        ]["volume"]

        if (
            previous_volume > 0
            and current["volume"] > previous_volume
        ):
            volume_up = True

    return {
        "close": current["close"],
        "momentum": momentum,
        "volume": current["volume"],
        "volume_up": volume_up,
        "count": len(recent_times)
    }


def run_index_replay(
    index_name,
    market,
    option_market
):

    # ==========================================
    # SPOT DATA
    # ==========================================

    spot_data = market.get_candles(
        index_name
    )

    spot_candles = get_candles(
        spot_data
    )

    spot_map = make_candle_map(
        spot_candles
    )

    times = sorted(
        t for t in spot_map
        if START_TIME <= t <= END_TIME
    )

    if not times:

        print(
            index_name,
            ": NO OPENING DATA"
        )

        return

    # ==========================================
    # OPTION CONTRACTS
    # ==========================================

    contracts = load_option_contracts(
        index_name
    )

    today = datetime.now().date()

    valid_expiries = sorted(
        set(
            c["expiry"]
            for c in contracts
            if c["expiry"] >= today
        )
    )

    if not valid_expiries:

        print(
            index_name,
            ": NO VALID EXPIRY"
        )

        return

    nearest_expiry = valid_expiries[0]

    gap = INDEX_CONFIG[
        index_name
    ]["strike_gap"]

    option_cache = {}

    # ==========================================
    # HEADER
    # ==========================================

    print(
        "\n"
        + "=" * 125
    )

    print(
        "ATM +/-2 BREADTH REPLAY"
    )

    print(
        "INDEX  :",
        index_name
    )

    print(
        "EXPIRY :",
        nearest_expiry
    )

    print(
        "\n"
        "TIME | SPOT | ATM | "
        "CE UP | PE DOWN | "
        "PE UP | CE DOWN | "
        "CE VOL | PE VOL | SIGNAL"
    )

    print(
        "-" * 125
    )

    # ==========================================
    # MINUTE REPLAY
    # ==========================================

    for i, current_time in enumerate(
        times
    ):

        spot = spot_map[
            current_time
        ]["close"]

        atm = calculate_atm(
            spot,
            gap
        )

        target_strikes = [
            atm + (
                offset * gap
            )
            for offset in range(
                -2,
                3
            )
        ]

        ce_up = 0
        ce_down = 0

        pe_up = 0
        pe_down = 0

        ce_volume_confirm = 0
        pe_volume_confirm = 0

        valid_ce = 0
        valid_pe = 0

        # ======================================
        # CHECK ATM +/-2 STRIKES
        # ======================================

        for strike in target_strikes:

            for option_type in [
                "CE",
                "PE"
            ]:

                contract = find_contract(
                    contracts,
                    nearest_expiry,
                    strike,
                    option_type
                )

                if not contract:
                    continue

                token = contract[
                    "token"
                ]

                if token not in option_cache:

                    data = (
                        option_market
                        .get_option_candles(
                            index_name,
                            token
                        )
                    )

                    option_cache[
                        token
                    ] = make_candle_map(
                        get_candles(
                            data
                        )
                    )

                candle_map = option_cache[
                    token
                ]

                info = get_same_contract_info(
                    candle_map,
                    current_time,
                    times
                )

                if not info:
                    continue

                # Need enough history for
                # confirmed breadth
                if info["count"] < 2:
                    continue

                momentum = info[
                    "momentum"
                ]

                if option_type == "CE":

                    valid_ce += 1

                    if momentum > 0:
                        ce_up += 1

                    elif momentum < 0:
                        ce_down += 1

                    if info[
                        "volume_up"
                    ]:
                        ce_volume_confirm += 1

                else:

                    valid_pe += 1

                    if momentum > 0:
                        pe_up += 1

                    elif momentum < 0:
                        pe_down += 1

                    if info[
                        "volume_up"
                    ]:
                        pe_volume_confirm += 1

        # ======================================
        # SPOT MOMENTUM
        # ======================================

        spot_momentum = 0

        if i >= 1:

            previous_time = times[
                i - 1
            ]

            spot_momentum = (
                spot
                - spot_map[
                    previous_time
                ]["close"]
            )

        # ======================================
        # SIGNAL LOGIC
        # ======================================

        signal = "WAIT"

        # CE WATCH:
        # Spot rising and option-chain breadth
        # supporting CE side.

        if (
            spot_momentum > 0
            and ce_up >= 3
            and pe_down >= 3
        ):

            signal = "CE WATCH"

        # CE ENTRY:
        # Strong breadth + some volume support.

        if (
            spot_momentum > 0
            and ce_up >= 4
            and pe_down >= 4
            and ce_volume_confirm >= 2
        ):

            signal = "CE ENTRY"

        # PE WATCH

        if (
            spot_momentum < 0
            and pe_up >= 3
            and ce_down >= 3
        ):

            signal = "PE WATCH"

        # PE ENTRY

        if (
            spot_momentum < 0
            and pe_up >= 4
            and ce_down >= 4
            and pe_volume_confirm >= 2
        ):

            signal = "PE ENTRY"

        # ======================================
        # OUTPUT
        # ======================================

        print(
            f"{current_time} | "
            f"{spot:.2f} | "
            f"{atm} | "
            f"{ce_up}/{valid_ce} | "
            f"{pe_down}/{valid_pe} | "
            f"{pe_up}/{valid_pe} | "
            f"{ce_down}/{valid_ce} | "
            f"{ce_volume_confirm}/{valid_ce} | "
            f"{pe_volume_confirm}/{valid_pe} | "
            f"{signal}"
        )


def main():

    market = MarketData()

    option_market = OptionMarketData()

    for index_name in [
        "NIFTY",
        "SENSEX"
    ]:

        run_index_replay(
            index_name,
            market,
            option_market
        )


if __name__ == "__main__":

    main()
