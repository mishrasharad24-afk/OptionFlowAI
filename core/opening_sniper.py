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


LOOKBACK = 5


def get_candles(data):
    return data.get("data", {}).get("candles") or []


# ==========================================================
# SPOT ANALYSIS
# ==========================================================

def analyze_spot(candles):

    if len(candles) < 3:
        return {
            "bull_score": 0,
            "bear_score": 0,
            "reason": ["Not enough spot candles"]
        }

    recent = candles[:LOOKBACK]

    bull = 0
    bear = 0
    reasons = []

    latest = recent[0]

    latest_open = float(latest[1])
    latest_high = float(latest[2])
    latest_low = float(latest[3])
    latest_close = float(latest[4])

    # Latest candle
    if latest_close > latest_open:
        bull += 1
        reasons.append("Spot latest candle bullish")

    elif latest_close < latest_open:
        bear += 1
        reasons.append("Spot latest candle bearish")

    # Candle breadth
    bullish_candles = 0
    bearish_candles = 0

    for candle in recent:

        o = float(candle[1])
        c = float(candle[4])

        if c > o:
            bullish_candles += 1

        elif c < o:
            bearish_candles += 1

    if bullish_candles >= 3:
        bull += 2
        reasons.append(
            f"Spot bullish breadth {bullish_candles}/{len(recent)}"
        )

    if bearish_candles >= 3:
        bear += 2
        reasons.append(
            f"Spot bearish breadth {bearish_candles}/{len(recent)}"
        )

    # Short-term momentum
    oldest_close = float(recent[-1][4])

    if latest_close > oldest_close:
        bull += 2
        reasons.append("Spot short-term momentum UP")

    elif latest_close < oldest_close:
        bear += 2
        reasons.append("Spot short-term momentum DOWN")

    # Close position inside latest candle
    candle_range = latest_high - latest_low

    if candle_range > 0:

        close_position = (
            latest_close - latest_low
        ) / candle_range

        if close_position >= 0.70:
            bull += 1
            reasons.append(
                "Spot closing near candle high"
            )

        elif close_position <= 0.30:
            bear += 1
            reasons.append(
                "Spot closing near candle low"
            )

    return {
        "bull_score": bull,
        "bear_score": bear,
        "reason": reasons
    }


# ==========================================================
# OPTION SIDE ANALYSIS
# ==========================================================

def analyze_option_side(
    index_name,
    contracts,
    option_type,
    option_market
):

    bullish_contracts = 0
    bearish_contracts = 0

    momentum_up = 0
    momentum_down = 0

    volume_acceleration = 0

    details = []

    for item in contracts:

        contract = item.get(
            option_type.lower()
        )

        if not contract:
            continue

        data = option_market.get_option_candles(
            index_name,
            contract["token"]
        )

        candles = get_candles(data)

        if len(candles) < 3:
            continue

        recent = candles[:LOOKBACK]

        latest = recent[0]

        latest_open = float(latest[1])
        latest_close = float(latest[4])
        latest_volume = float(latest[5])

        previous_close = float(recent[1][4])
        previous_volume = float(recent[1][5])

        oldest_close = float(recent[-1][4])

        # Latest candle direction
        if latest_close > latest_open:
            bullish_contracts += 1

        elif latest_close < latest_open:
            bearish_contracts += 1

        # Premium momentum
        if latest_close > oldest_close:
            momentum_up += 1

        elif latest_close < oldest_close:
            momentum_down += 1

        # Volume acceleration
        if (
            previous_volume > 0
            and latest_volume > previous_volume * 1.20
        ):
            volume_acceleration += 1

        details.append({
            "strike": item["strike"],
            "type": option_type,
            "token": contract["token"],
            "close": latest_close,
            "previous_close": previous_close,
            "oldest_close": oldest_close,
            "volume": latest_volume
        })

    score = 0
    reasons = []

    if bullish_contracts >= 3:

        score += 2

        reasons.append(
            f"{option_type} bullish breadth "
            f"{bullish_contracts}/5"
        )

    if momentum_up >= 3:

        score += 3

        reasons.append(
            f"{option_type} premium momentum UP "
            f"{momentum_up}/5"
        )

    if volume_acceleration >= 2:

        score += 2

        reasons.append(
            f"{option_type} volume acceleration "
            f"{volume_acceleration}/5"
        )

    return {
        "score": score,
        "bullish": bullish_contracts,
        "bearish": bearish_contracts,
        "momentum_up": momentum_up,
        "momentum_down": momentum_down,
        "volume_acceleration": volume_acceleration,
        "reasons": reasons,
        "details": details
    }


# ==========================================================
# OPENING SNIPER
# ==========================================================

def run_opening_sniper(index_name):

    market = MarketData()
    option_market = OptionMarketData()

    # -----------------------------
    # GET SPOT DATA
    # -----------------------------

    spot_data = market.get_candles(
        index_name
    )

    spot_candles = get_candles(
        spot_data
    )

    if not spot_candles:

        return {
            "status": "error",
            "message": "No spot candles"
        }

    spot = float(
        spot_candles[0][4]
    )

    # -----------------------------
    # SELECT ATM +/- 2 OPTIONS
    # -----------------------------

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

    # -----------------------------
    # ANALYZE SPOT
    # -----------------------------

    spot_analysis = analyze_spot(
        spot_candles
    )

    # -----------------------------
    # ANALYZE CE
    # -----------------------------

    ce_analysis = analyze_option_side(
        index_name,
        selected["strikes"],
        "CE",
        option_market
    )

    # -----------------------------
    # ANALYZE PE
    # -----------------------------

    pe_analysis = analyze_option_side(
        index_name,
        selected["strikes"],
        "PE",
        option_market
    )

    # ======================================================
    # SCORES
    # ======================================================

    ce_score = (
        spot_analysis["bull_score"]
        + ce_analysis["score"]
    )

    pe_score = (
        spot_analysis["bear_score"]
        + pe_analysis["score"]
    )

    # ======================================================
    # SPOT DIRECTION GATE
    # ======================================================

    spot_bull = spot_analysis[
        "bull_score"
    ]

    spot_bear = spot_analysis[
        "bear_score"
    ]

    if spot_bull > spot_bear:

        spot_direction = "UP"

    elif spot_bear > spot_bull:

        spot_direction = "DOWN"

    else:

        spot_direction = "NEUTRAL"

    # ======================================================
    # OPTION CONFIRMATION
    # ======================================================

    ce_confirm = (
        ce_analysis["momentum_up"] >= 3
        and
        ce_analysis["bullish"] >= 3
    )

    pe_confirm = (
        pe_analysis["momentum_up"] >= 3
        and
        pe_analysis["bullish"] >= 3
    )

    # ======================================================
    # FINAL DECISION
    # ======================================================

    decision = "WAIT"

    if spot_direction == "UP":

        if (
            ce_confirm
            and ce_score >= 7
            and ce_score > pe_score
        ):

            decision = "CE"

        elif (
            pe_confirm
            and not ce_confirm
        ):

            decision = "CONFLICT"

    elif spot_direction == "DOWN":

        if (
            pe_confirm
            and pe_score >= 7
            and pe_score > ce_score
        ):

            decision = "PE"

        elif (
            ce_confirm
            and not pe_confirm
        ):

            decision = "CONFLICT"

    # ======================================================
    # RESULT
    # ======================================================

    return {
        "status": "success",

        "index": index_name,
        "spot": spot,
        "atm": selected["atm"],
        "expiry": selected["expiry"],

        "spot_direction": spot_direction,

        "ce_score": ce_score,
        "pe_score": pe_score,

        "ce_confirm": ce_confirm,
        "pe_confirm": pe_confirm,

        "decision": decision,

        "spot_analysis": spot_analysis,
        "ce_analysis": ce_analysis,
        "pe_analysis": pe_analysis
    }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    for index_name in [
        "NIFTY",
        "SENSEX"
    ]:

        result = run_opening_sniper(
            index_name
        )

        print(
            "\n"
            + "=" * 70
        )

        if result["status"] != "success":

            print(
                index_name,
                result
            )

            continue

        print(
            "OPENING SNIPER TEST"
        )

        print(
            "INDEX     :",
            result["index"]
        )

        print(
            "SPOT      :",
            result["spot"]
        )

        print(
            "ATM       :",
            result["atm"]
        )

        print(
            "EXPIRY    :",
            result["expiry"]
        )

        print(
            "SPOT DIR  :",
            result["spot_direction"]
        )

        print(
            "CE SCORE  :",
            result["ce_score"]
        )

        print(
            "PE SCORE  :",
            result["pe_score"]
        )

        print(
            "CE CONF   :",
            result["ce_confirm"]
        )

        print(
            "PE CONF   :",
            result["pe_confirm"]
        )

        print(
            "DECISION  :",
            result["decision"]
        )

        print(
            "\nSPOT REASONS:"
        )

        for reason in result[
            "spot_analysis"
        ]["reason"]:

            print(
                "-",
                reason
            )

        print(
            "\nCE REASONS:"
        )

        for reason in result[
            "ce_analysis"
        ]["reasons"]:

            print(
                "-",
                reason
            )

        print(
            "\nPE REASONS:"
        )

        for reason in result[
            "pe_analysis"
        ]["reasons"]:

            print(
                "-",
                reason
            )
