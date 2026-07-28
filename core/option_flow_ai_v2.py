from core.mstock_option_chain import get_atm_option_chain


class OptionFlowAI:

    def __init__(self, depth=2):
        self.depth = depth

    def analyze(self):
        return get_atm_option_chain(depth=self.depth)

    def summary(self):
        data = self.analyze()

        if not data:
            print("ERROR : Option chain not available.")
            return

        ce_buy = sum(x.get("buy", 0) for x in data["calls"])
        ce_sell = sum(x.get("sell", 0) for x in data["calls"])

        pe_buy = sum(x.get("buy", 0) for x in data["puts"])
        pe_sell = sum(x.get("sell", 0) for x in data["puts"])

        ce_ratio = ce_buy / ce_sell if ce_sell else 0
        pe_ratio = pe_buy / pe_sell if pe_sell else 0

        writer_strength = ce_sell + pe_sell
        buyer_strength = ce_buy + pe_buy

        if ce_ratio > pe_ratio:
            bias = "BULLISH"
        elif pe_ratio > ce_ratio:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        total = ce_ratio + pe_ratio
        confidence = abs(ce_ratio - pe_ratio) / total * 100 if total else 0

        if confidence < 10:
            signal = "NO TRADE"
        elif bias == "BULLISH":
            signal = "BUY CE"
        elif bias == "BEARISH":
            signal = "BUY PE"
        else:
            signal = "NO TRADE"

        print("=" * 60)
        print("OPTION FLOW AI V2")
        print("=" * 60)

        print(f"Spot              : {data['spot']}")
        print(f"ATM Strike        : {data['atm']}")
        print()

        print(f"CE Buy            : {ce_buy:,}")
        print(f"CE Sell           : {ce_sell:,}")
        print(f"CE Ratio          : {ce_ratio:.3f}")
        print()

        print(f"PE Buy            : {pe_buy:,}")
        print(f"PE Sell           : {pe_sell:,}")
        print(f"PE Ratio          : {pe_ratio:.3f}")
        print()

        print(f"Buyer Strength    : {buyer_strength:,}")
        print(f"Writer Strength   : {writer_strength:,}")
        print()

        print(f"Market Bias       : {bias}")
        print(f"Confidence        : {confidence:.2f}%")
        print()
        print(f"FINAL SIGNAL      : {signal}")
        print("=" * 60)


if __name__ == "__main__":
    bot = OptionFlowAI(depth=2)
    bot.summary()

