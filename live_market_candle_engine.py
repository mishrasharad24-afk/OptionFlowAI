from live_candle_builder import LiveCandleBuilder


class LiveMarketCandleEngine:

    def __init__(self):
        self.builder_5m = LiveCandleBuilder(5)
        self.builder_15m = LiveCandleBuilder(15)

    def update(self, symbol, price, timestamp=None):

        completed_5m = self.builder_5m.update(
            symbol,
            price,
            timestamp,
        )

        completed_15m = self.builder_15m.update(
            symbol,
            price,
            timestamp,
        )

        return {
            "completed_5m": completed_5m,
            "completed_15m": completed_15m,
            "current_5m": self.builder_5m.get_current(symbol),
            "current_15m": self.builder_15m.get_current(symbol),
        }

    @staticmethod
    def candle_to_row(candle):

        if not candle:
            return None

        return [
            candle["timestamp"],
            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"],
            candle.get("volume", 0),
        ]
