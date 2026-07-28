"""
OptionFlowAI V2
market_structure_v2.py
"""

from __future__ import annotations

import logging

logger = logging.getLogger("OptionFlowAI")


class MarketStructure:

    def __init__(self):
        self.last_signal = {}

    def analyze(self, candles):

        if len(candles) < 3:
            return {
                "trend": "UNKNOWN",
                "bos": False,
                "choch": False,
                "hh": False,
                "hl": False,
                "lh": False,
                "ll": False,
            }

        c1 = candles[-3]
        c2 = candles[-2]
        c3 = candles[-1]

        hh = c3["high"] > c2["high"]
        hl = c3["low"] > c2["low"]

        lh = c3["high"] < c2["high"]
        ll = c3["low"] < c2["low"]

        trend = "SIDEWAYS"

        if hh and hl:
            trend = "BULLISH"

        elif lh and ll:
            trend = "BEARISH"

        bos = (
            c3["close"] > c2["high"] or
            c3["close"] < c2["low"]
        )

        choch = (
            (hh and ll) or
            (lh and hl)
        )

        return {
            "trend": trend,
            "bos": bos,
            "choch": choch,
            "hh": hh,
            "hl": hl,
            "lh": lh,
            "ll": ll,
        }


structure = MarketStructure()

