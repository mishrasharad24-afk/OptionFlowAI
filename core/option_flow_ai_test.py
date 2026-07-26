import json
from core.mstock_option_chain import get_atm_option_chain

WEIGHTS = {
    0: 5,
    1: 3,
    2: 1,
}

class OptionFlowAI:

    def __init__(self, depth=2):
        self.depth = depth

    def _weight(self, strike, atm, step):
        distance = abs(strike - atm) // step
        return WEIGHTS.get(distance, 0)

    def _weighted_row(self, item, atm, step):
        buy = int(item["buy"])
        sell = int(item["sell"])

        weight = self._weight(
            item["strike"],
            atm,
            step,
        )

        raw = buy - sell

        return {
            "token": item["token"],
            "strike": item["strike"],
            "buy": buy,
            "sell": sell,
            "weight": weight,
            "raw_score": raw,
            "weighted_score": raw * weight,
        }

    def _weighted_side(self, rows, atm, step):
        details = []

        total_buy = 0
        total_sell = 0
        total_raw = 0
        total_weighted = 0        for item in rows:

            row = self._weighted_row(
                item,
                atm,
                step,
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
            "details": details,
        }

    def analyze(self):

        data = get_atm_option_chain(
            depth=self.depth,
        )

        ce = self._weighted_side(
            data["calls"],
            data["atm"],
            data["step"],
        )

        pe = self._weighted_side(
            data["puts"],
            data["atm"],
            data["step"],
        )

        return {
            "spot": data["spot"],
            "atm": data["atm"],
            "step": data["step"],
            "ce": ce,
            "pe": pe,
        }    def summary(self):

        result = self.analyze()

        print("=" * 60)
        print("OPTION FLOW AI")
        print("=" * 60)

        print(f"Spot : {result['spot']}")
        print(f"ATM  : {result['atm']}")
        print()

        print("CALL SIDE")
        print(json.dumps(result["ce"], indent=2))

        print()

        print("PUT SIDE")
        print(json.dumps(result["pe"], indent=2))


if __name__ == "__main__":

    bot = OptionFlowAI(depth=2)
    bot.summary()
