import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from core.market_data import MarketData
from core.strike_selector import select_nearby_options
from core.option_market_data import OptionMarketData


def get_latest_candle(data):

    candles = data.get(
        "data", {}
    ).get("candles")

    if not candles:
        return None

    return candles[0]


def build_option_flow_snapshot(index_name):

    market = MarketData()
    option_market = OptionMarketData()

    # ------------------------------------------
    # GET SPOT
    # ------------------------------------------

    spot_data = market.get_candles(index_name)

    spot_candles = spot_data.get(
        "data", {}
    ).get("candles")

    if not spot_candles:
        return {
            "status": "error",
            "message": "No spot data"
        }

    spot = float(spot_candles[0][4])

    # ------------------------------------------
    # SELECT ATM +/- 2 STRIKES
    # ------------------------------------------

    selected = select_nearby_options(
        index_name,
        spot,
        wings=2
    )

    if not selected:
        return {
            "status": "error",
            "message": "No option contracts"
        }

    snapshot = []

    ce_total_volume = 0
    pe_total_volume = 0

    ce_bullish = 0
    pe_bullish = 0

    # ------------------------------------------
    # FETCH OPTION DATA
    # ------------------------------------------

    for item in selected["strikes"]:

        strike = item["strike"]

        for option_type in ["ce", "pe"]:

            contract = item[option_type]

            if not contract:
                continue

            data = option_market.get_option_candles(
                index_name,
                contract["token"]
            )

            candle = get_latest_candle(data)

            if not candle:
                continue

            time = candle[0]
            open_price = float(candle[1])
            high = float(candle[2])
            low = float(candle[3])
            close = float(candle[4])
            volume = float(candle[5])

            change = close - open_price

            bullish = close > open_price

            if option_type == "ce":

                ce_total_volume += volume

                if bullish:
                    ce_bullish += 1

            else:

                pe_total_volume += volume

                if bullish:
                    pe_bullish += 1

            snapshot.append({
                "strike": strike,
                "type": option_type.upper(),
                "token": contract["token"],
                "symbol": contract["symbol"],
                "time": time,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "change": round(change, 2),
                "volume": volume
            })

    # ------------------------------------------
    # SIMPLE FLOW SCORE
    # ------------------------------------------

    ce_score = ce_bullish
    pe_score = pe_bullish

    if ce_score > pe_score:

        bias = "CE"

    elif pe_score > ce_score:

        bias = "PE"

    else:

        bias = "NEUTRAL"

    return {
        "status": "success",
        "index": index_name,
        "spot": spot,
        "atm": selected["atm"],
        "expiry": selected["expiry"],
        "ce_bullish": ce_bullish,
        "pe_bullish": pe_bullish,
        "ce_volume": ce_total_volume,
        "pe_volume": pe_total_volume,
        "bias": bias,
        "snapshot": snapshot
    }


# ==================================================
# TEST
# ==================================================

if __name__ == "__main__":

    for index_name in ["NIFTY", "SENSEX"]:

        result = build_option_flow_snapshot(
            index_name
        )

        print("\n" + "=" * 70)

        if result["status"] != "success":

            print(index_name, result)

            continue

        print("INDEX      :", result["index"])
        print("SPOT       :", result["spot"])
        print("ATM        :", result["atm"])
        print("EXPIRY     :", result["expiry"])

        print(
            "CE BULLISH :",
            result["ce_bullish"],
            "/ 5"
        )

        print(
            "PE BULLISH :",
            result["pe_bullish"],
            "/ 5"
        )

        print(
            "CE VOLUME  :",
            int(result["ce_volume"])
        )

        print(
            "PE VOLUME  :",
            int(result["pe_volume"])
        )

        print(
            "FLOW BIAS  :",
            result["bias"]
        )

        print("\nOPTION DETAILS")

        for item in result["snapshot"]:

            print(
                item["strike"],
                item["type"],
                "Close:",
                item["close"],
                "Change:",
                item["change"],
                "Vol:",
                int(item["volume"])
            )
