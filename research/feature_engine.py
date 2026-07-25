class FeatureEngine:

    def extract(self, candles):

        if len(candles) < 2:
            return None

        first = candles[0]
        last = candles[-1]

        open_price = first[1]
        close_price = last[4]

        day_high = max(c[2] for c in candles)
        day_low = min(c[3] for c in candles)

        total_volume = sum(c[5] for c in candles)

        direction = "SIDEWAYS"

        if close_price > open_price:
            direction = "BULLISH"

        elif close_price < open_price:
            direction = "BEARISH"

        return {
            "open": open_price,
            "close": close_price,
            "high": day_high,
            "low": day_low,
            "range": day_high - day_low,
            "direction": direction,
            "volume": total_volume,
            "candles": len(candles)
        }
