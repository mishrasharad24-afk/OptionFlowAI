"""
OptionFlowAI V2
candle_engine_v2.py
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict

logger = logging.getLogger("OptionFlowAI")


class CandleEngine:

    def __init__(self):
        self.current = {}
        self.history = defaultdict(list)

    def update_tick(self, token, price, volume=0):

        token = str(token)

        now = int(time.time())
        bucket = now - (now % 60)

        key = (token, bucket)

        if key not in self.current:

            self.current[key] = {
                "time": bucket,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }

            return

        candle = self.current[key]

        candle["high"] = max(candle["high"], price)
        candle["low"] = min(candle["low"], price)
        candle["close"] = price
        candle["volume"] += volume

    def finalize(self):

        now = int(time.time())
        current_bucket = now - (now % 60)

        remove = []

        for key, candle in self.current.items():

            token, bucket = key

            if bucket >= current_bucket:
                continue

            self.history[token].append(candle)

            if len(self.history[token]) > 1000:
                self.history[token] = self.history[token][-1000:]

            remove.append(key)

        for key in remove:
            del self.current[key]

    def get_history(self, token, limit=100):

        token = str(token)

        return self.history[token][-limit:]

    def get_last_closed(self, token):

        candles = self.get_history(token, 1)

        if candles:
            return candles[-1]

        return None

    def get_live(self, token):

        token = str(token)

        now = int(time.time())
        bucket = now - (now % 60)

        return self.current.get((token, bucket))


engine = CandleEngine()

