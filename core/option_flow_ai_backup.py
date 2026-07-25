import json
from core.mstock_option_chain import (
    get_atm_option_chain,
    get_option_ltp,
)


WEIGHTS = {
    0: 5,   # ATM
    1: 3,   # ATM ±1
    2: 1,   # ATM ±2
}


class OptionFlowAI:

    def __init__(self, depth=2):
        self.depth = depth

    def _weight(self, strike, atm, step):
        distance = abs(strike - atm) // step
        return WEIGHTS.get(distance, 0)

    def _weighted_row(self, item, atm, step):
    buy = int(item.get("buy", 0))
    sell = int(item.get("sell", 0))

    weight = self._weight(
        item["strike"],
        atm,
        step,
    )

    raw_score = buy - sell
    weighted_score = raw_score * weight

    ltp_info = get_option_ltp(item["token"])

    premium = None

    if ltp_info:
        premium = ltp_info["ltp"]

    return {
        "token": item["token"],
        "strike": item["strike"],
        "weight": weight,
        "buy": buy,
        "sell": sell,
        "premium": premium,
        "raw_score": raw_score,
        "weighted_score": weighted_score,
    }
    

       

    def _weighted_side(
        self,
        strikes,
        atm,
        step
    ):

        total_buy = 0
        total_sell = 0
        total_raw = 0
        total_weighted = 0

        details = []

        for item in strikes:

            row = self._weighted_row(
                item,
                atm,
                step
            )

            details.append(row)

            total_buy += row["buy"]
            total_sell += row["sell"]
            total_raw += row["raw_score"]
            total_weighted += row["weighted_score"]

        return {
            "buy": total_buy,
            "sell": total_sell,
            "raw_score": total_raw,
            "weighted_score": total_weighted,
            "details": details
        }
    def analyze(self):

        chain = get_atm_option_chain(depth=self.depth)

        if chain is None:
            return None

        atm = chain["atm"]
        step = chain["step"]

        ce = self._weighted_side(
            chain["calls"],
            atm,
            step
        )

        pe = self._weighted_side(
            chain["puts"],
            atm,
            step
        )

        ce_score = ce["weighted_score"]
        pe_score = pe["weighted_score"]

        bias = pe_score - ce_score

        total = abs(ce_score) + abs(pe_score)

        if total == 0:
            confidence = 0
        else:
            confidence = round(
                abs(bias) * 100 / total
            )

        if confidence >= 60:
            strength = "STRONG"
        elif confidence >= 35:
            strength = "NORMAL"
        else:
            strength = "WEAK"

        if confidence < 20:
            signal = "NO TRADE"
        elif bias > 0:
            if confidence >= 60:
                signal = "STRONG CE"
            else:
                signal = "CE"
        else:
            if confidence >= 60:
                signal = "STRONG PE"
            else:
                signal = "PE"

        return {
            "spot": chain["spot"],
            "atm": atm,
            "step": step,
            "ce": ce,
            "pe": pe,
            "ce_score": ce_score,
            "pe_score": pe_score,
            "bias": bias,
            "confidence": confidence,
            "strength": strength,
            "signal": signal
        }
    def summary(self):

        data = self.analyze()

        if data is None:
            return None

        return {
            "spot": data["spot"],
            "atm": data["atm"],
            "step": data["step"],
            "ce_score": data["ce_score"],
            "pe_score": data["pe_score"],
            "bias": data["bias"],
            "confidence": data["confidence"],
            "strength": data["strength"],
            "signal": data["signal"]
        }


if __name__ == "__main__":

    engine = OptionFlowAI(depth=2)

    result = engine.analyze()

    if result is None:
        print("No option chain available.")

    else:

        print("=" * 60)
        print("OPTION FLOW AI V2")
        print("=" * 60)

        print(
            json.dumps(
                result,
                indent=4
            )
        )

        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)

        print(
            json.dumps(
                engine.summary(),
                indent=4
            )
        )

