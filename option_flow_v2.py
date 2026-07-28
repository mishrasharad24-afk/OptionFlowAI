"""
OptionFlowAI V2
option_flow_v2.py
"""

from __future__ import annotations

import logging

logger = logging.getLogger("OptionFlowAI")


class OptionFlowEngine:

    def __init__(self):
        self.data = {}

    def update(self, token, ltp, volume=0, oi=0):

        token = str(token)

        self.data[token] = {
            "ltp": float(ltp),
            "volume": volume,
            "oi": oi,
        }

    def get(self, token):

        return self.data.get(str(token))

    def signal(self, ce_token, pe_token):

        ce = self.get(ce_token)
        pe = self.get(pe_token)

        if not ce or not pe:
            return "WAIT"

        if ce["ltp"] > pe["ltp"] * 1.20:
            return "CE"

        if pe["ltp"] > ce["ltp"] * 1.20:
            return "PE"

        return "WAIT"


option_flow = OptionFlowEngine()

