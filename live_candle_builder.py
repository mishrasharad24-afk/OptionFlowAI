from datetime import datetime


class LiveCandleBuilder:

    def __init__(self, timeframe_minutes=5):
        self.timeframe_minutes = timeframe_minutes
        self.current = {}

    def _bucket_time(self, now):
        minute = (
            now.minute
            // self.timeframe_minutes
            * self.timeframe_minutes
        )

        return now.replace(
            minute=minute,
            second=0,
            microsecond=0,
        )

    def update(self, symbol, price, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now()

        price = float(price)
        bucket = self._bucket_time(timestamp)

        candle = self.current.get(symbol)

        # First tick
        if candle is None:
            self.current[symbol] = {
                "timestamp": bucket.isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 0,
            }

            return None

        old_bucket = datetime.fromisoformat(
            candle["timestamp"]
        )

        # Same 5-minute candle
        if bucket == old_bucket:
            candle["high"] = max(
                candle["high"],
                price,
            )

            candle["low"] = min(
                candle["low"],
                price,
            )

            candle["close"] = price

            return None

        # New 5-minute candle started.
        # Return completed previous candle.
        completed = dict(candle)

        self.current[symbol] = {
            "timestamp": bucket.isoformat(),
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 0,
        }

        return completed

    def get_current(self, symbol):
        candle = self.current.get(symbol)

        if candle is None:
            return None

        return dict(candle)
