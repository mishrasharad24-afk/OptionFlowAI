"""
OptionFlowAI V2
ai_engine_v2.py
"""

from __future__ import annotations

import logging

logger = logging.getLogger("OptionFlowAI")


class AIEngine:

    def decide(self, structure, option_signal):

        trend = structure.get("trend", "UNKNOWN")
        bos = structure.get("bos", False)
        choch = structure.get("choch", False)

        if trend == "BULLISH" and bos and option_signal == "CE":
            return {
                "action": "BUY_CE",
                "confidence": 90,
            }

        if trend == "BEARISH" and bos and option_signal == "PE":
            return {
                "action": "BUY_PE",
                "confidence": 90,
            }

        if choch:
            return {
                "action": "WAIT",
                "confidence": 40,
            }

        return {
            "action": "WAIT",
            "confidence": 0,
        }


ai = AIEngine()

