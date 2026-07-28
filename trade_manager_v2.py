"""
OptionFlowAI V2
trade_manager_v2.py
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("OptionFlowAI")


class TradeManager:

    def __init__(self):
        self.position = None
        self.history = []

    def can_enter(self):
        return self.position is None

    def enter(self, signal, price):

        if not self.can_enter():
            return False

        self.position = {
            "side": signal,
            "entry": float(price),
            "time": datetime.now(),
        }

        logger.info(f"ENTRY : {signal} @ {price}")
        return True

    def exit(self, price):

        if self.position is None:
            return None

        trade = self.position.copy()
        trade["exit"] = float(price)
        trade["exit_time"] = datetime.now()

        if trade["side"] == "BUY_CE":
            trade["pnl"] = trade["exit"] - trade["entry"]
        else:
            trade["pnl"] = trade["exit"] - trade["entry"]

        self.history.append(trade)
        self.position = None

        logger.info(f"EXIT : {trade}")

        return trade

    def status(self):
        return self.position


trade_manager = TradeManager()

