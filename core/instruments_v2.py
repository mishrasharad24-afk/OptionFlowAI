"""
OptionFlowAI V2
core/instruments_v2.py
Phase-1
"""

from __future__ import annotations

import csv
import logging

from pathlib import Path
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("OptionFlowAI")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MASTER_FILE = PROJECT_ROOT / "instrument_master.csv"


INDEX_CONFIG = {

    "SENSEX": {

        "spot_token": 51,
        "exchange": "BSE",
        "option_exchange": "BFO",
        "strike_step": 100,

    },

    "NIFTY": {

        "spot_token": 26000,
        "exchange": "NSE",
        "option_exchange": "NFO",
        "strike_step": 50,

    },

}


class InstrumentManager:

    def __init__(self):

        self.loaded = False

        self.rows = []

        self.lookup = {}

        self.option_rows = defaultdict(list)

        self.expiry_map = defaultdict(set)

        self.spot_tokens = {}

    def load(self):

        if self.loaded:
            return

        logger.info("Loading Instrument Master...")

        with open(MASTER_FILE,
                  newline="",
                  encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:

                self.rows.append(row)

                token = row.get("instrument_token")

                if token:

                    self.lookup[token] = row

                if row.get("segment") == "OPTIDX":

                    name = row.get("name", "")

                    self.option_rows[name].append(row)

                    expiry = row.get("expiry")

                    if expiry:

                        self.expiry_map[name].add(expiry)

        self.spot_tokens["SENSEX"] = \
            INDEX_CONFIG["SENSEX"]["spot_token"]

        self.spot_tokens["NIFTY"] = \
            INDEX_CONFIG["NIFTY"]["spot_token"]

        self.loaded = True

        logger.info(
            "Instrument Master Loaded : %d rows",
            len(self.rows)
        )


manager = InstrumentManager()

manager.load()

# ---------- PART-1 END ----------

def get_spot_token(self, index_name):

    return self.spot_tokens.get(index_name)


def get_nearest_expiry(self, index_name):

    expiries = sorted(self.expiry_map.get(index_name, []))

    if not expiries:
        return None

    today = datetime.now().date()

    for exp in expiries:

        try:
            d = datetime.strptime(exp, "%Y-%m-%d").date()

            if d >= today:
                return exp

        except Exception:
            pass

    return expiries[-1]


def get_atm_strike(self, index_name, spot_price):

    step = INDEX_CONFIG[index_name]["strike_step"]

    return round(float(spot_price) / step) * step


# ---------- PART-2 END ----------

def get_option_by_strike(
    self,
    index_name,
    expiry,
    strike,
    option_type,
):

    rows = self.option_rows.get(index_name, [])

    strike = int(strike)

    option_type = option_type.upper()

    for row in rows:

        if row.get("expiry") != expiry:
            continue

        try:
            row_strike = int(float(row.get("strike_price", 0)))
        except Exception:
            continue

        if row_strike != strike:
            continue

        opt = row.get("option_type", "").upper()

        if opt == option_type:
            return row

    return None


def get_option_zone(self, index_name, spot_price):

    expiry = self.get_nearest_expiry(index_name)

    atm = self.get_atm_strike(index_name, spot_price)

    step = INDEX_CONFIG[index_name]["strike_step"]

    result = {}

    for offset in (-2, -1, 0, 1, 2):

        strike = atm + (offset * step)

        result[offset] = {

            "strike": strike,

            "CE": self.get_option_by_strike(
                index_name,
                expiry,
                strike,
                "CE",
            ),

            "PE": self.get_option_by_strike(
                index_name,
                expiry,
                strike,
                "PE",
            ),
        }

    return result


# ---------- PART-3 END ----------

def get_token(self, option_row):

    if not option_row:
        return None

    return option_row.get("instrument_token")


def get_trading_symbol(self, option_row):

    if not option_row:
        return None

    return (
        option_row.get("trading_symbol")
        or option_row.get("symbol")
        or option_row.get("tradingsymbol")
    )


def get_exchange(self, option_row):

    if not option_row:
        return None

    return (
        option_row.get("exchange")
        or option_row.get("segment")
    )


def get_complete_option_set(self, index_name, spot_price):

    zone = self.get_option_zone(index_name, spot_price)

    output = {}

    for level, data in zone.items():

        output[level] = {

            "strike": data["strike"],

            "CE": {
                "token": self.get_token(data["CE"]),
                "symbol": self.get_trading_symbol(data["CE"]),
                "exchange": self.get_exchange(data["CE"]),
            },

            "PE": {
                "token": self.get_token(data["PE"]),
                "symbol": self.get_trading_symbol(data["PE"]),
                "exchange": self.get_exchange(data["PE"]),
            },
        }

    return output



# ---------- PART-4 END ----------

