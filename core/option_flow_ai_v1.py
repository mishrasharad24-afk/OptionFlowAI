import json
from core.mstock_option_chain import get_atm_option_chain


class OptionFlowAI:

    def __init__(self, depth=2):
        self.depth = depth

    def _strike_score(self, item):
        buy = int(item.get("buy", 0))
        sell = int(item.get("sell", 0))

        score = buy - sell

        return {
            "strike": item["strike"],
            "buy": buy,
            "sell": sell,
            "score": score
        }

    def _side_score(self, strikes):
        total_buy = 0
        total_sell = 0
        total_score = 0

        details = []

        for item in strikes:

            row = self._strike_score(item)

            details.append(row)

            total_buy += row["buy"]
            total_sell += row["sell"]
            total_score += row["score"]

        return {
            "buy": total_buy,
            "sell": total_sell,
            "score": total_score,
            "details": details
        }

    def analyze(self):

        chain = get_atm_option_chain(depth=self.depth)

        if chain is None:
            return None

        ce = self._side_score(chain["calls"])
        pe = self._side_score(chain["puts"])

        return {
            "spot": chain["spot"],
            "atm": chain["atm"],
            "step": chain["step"],
            "ce": ce,
            "pe": pe
        }
    def _confidence(self, bias, ce_score, pe_score):

        total = abs(ce_score) + abs(pe_score)

        if total == 0:
            return 0

        value = abs(bias) / total

        confidence = round(value * 100)

        if confidence > 100:
            confidence = 100

        return confidence

    def _signal(self, bias, confidence):

        if confidence < 15:
            return "NO TRADE"

        if bias > 0:
            if confidence >= 60:
                return "STRONG CE"
            elif confidence >= 30:
                return "CE"

        if bias < 0:
            if confidence >= 60:
                return "STRONG PE"
            elif confidence >= 30:
                return "PE"

        return "NO TRADE"

    def run(self):

        data = self.analyze()

        if data is None:
            return None

        ce_score = data["ce"]["score"]
        pe_score = data["pe"]["score"]

        bias = pe_score - ce_score

        confidence = self._confidence(
            bias,
            ce_score,
            pe_score
        )

        signal = self._signal(
            bias,
            confidence
        )

        data["bias"] = bias
        data["confidence"] = confidence
        data["signal"] = signal

        return data
    def summary(self):

        result = self.run()

        if result is None:
            return None

        return {
            "spot": result["spot"],
            "atm": result["atm"],
            "step": result["step"],
            "ce_score": result["ce"]["score"],
            "pe_score": result["pe"]["score"],
            "bias": result["bias"],
            "confidence": result["confidence"],
            "signal": result["signal"]
        }


if __name__ == "__main__":

    engine = OptionFlowAI(depth=2)

    result = engine.run()

    if result is None:
        print("No option chain available.")

    else:

        print("=" * 60)
        print("OPTION FLOW AI")
        print("=" * 60)

        print(json.dumps(
            result,
            indent=4
        ))

        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)

        print(json.dumps(
            engine.summary(),
            indent=4
        ))

