# ============================================================
# FINAL AI DECISION ENGINE
# Part 1/4
#
# Purpose:
# 5M + 15M historical edge
# + market regime
# + price action
# + previous-day context
# + BUY_ABOVE / BUY_AROUND
# => Final AI-style decision score
# ============================================================

import os
import sys
import math
import json
import traceback
from datetime import datetime
from collections import defaultdict

# ------------------------------------------------------------
# PROJECT PATH
# ------------------------------------------------------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(CURRENT_DIR)

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Existing research engines
import historical.price_action_regime_research as pa_research
import historical.trade_style_backtest as trade_research


# ============================================================
# ENGINE CONFIG
# ============================================================

INDEXES = (
    "NIFTY",
    "SENSEX",
)

AI_TIMEFRAMES = (
    "5M",
    "15M",
    "5M+15M",
)

# Minimum historical sample required before an edge
# receives normal confidence.
MIN_SAMPLE_SIZE = 20

# Stronger confidence threshold.
STRONG_SAMPLE_SIZE = 40

# Historical performance filters.
MIN_WIN_RATE = 50.0
MIN_PROFIT_FACTOR = 1.20
MIN_EXPECTANCY = 0.0

# Decision score thresholds.
HIGH_CONFIDENCE_SCORE = 75.0
MEDIUM_CONFIDENCE_SCORE = 60.0

# Maximum drawdown penalty starts becoming stronger
# above this level.
DD_WARNING_R = 5.0

# ------------------------------------------------------------
# COMPONENT WEIGHTS
# ------------------------------------------------------------

WEIGHTS = {
    "win_rate": 0.22,
    "expectancy": 0.20,
    "profit_factor": 0.18,
    "sample_size": 0.10,
    "drawdown": 0.10,
    "timeframe_agreement": 0.08,
    "regime_match": 0.05,
    "price_action": 0.04,
    "previous_day": 0.03,
}


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        result = float(value)

        if math.isnan(result):
            return default

        if math.isinf(result):
            return default

        return result

    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default

        return int(float(value))

    except Exception:
        return default


def clamp(value, low, high):
    return max(
        low,
        min(
            high,
            value,
        ),
    )


def normalize_direction(direction):
    value = str(
        direction or ""
    ).strip().upper()

    if value in (
        "BULL",
        "BULLISH",
        "CE",
        "CALL",
        "UP",
        "LONG",
    ):
        return "BULLISH"

    if value in (
        "BEAR",
        "BEARISH",
        "PE",
        "PUT",
        "DOWN",
        "SHORT",
    ):
        return "BEARISH"

    return "NEUTRAL"


def normalize_entry_style(style):
    value = str(
        style or ""
    ).strip().upper()

    value = value.replace(
        " ",
        "_",
    )

    if value in (
        "BUY_ABOVE",
        "ABOVE",
    ):
        return "BUY_ABOVE"

    if value in (
        "BUY_AROUND",
        "AROUND",
    ):
        return "BUY_AROUND"

    return "UNKNOWN"


def normalize_timeframe(timeframe):
    value = str(
        timeframe or ""
    ).strip().upper()

    aliases = {
        "5": "5M",
        "5MIN": "5M",
        "5MINUTE": "5M",

        "15": "15M",
        "15MIN": "15M",
        "15MINUTE": "15M",

        "5M15M": "5M+15M",
        "5M_15M": "5M+15M",
        "15M+5M": "5M+15M",
    }

    return aliases.get(
        value,
        value,
    )


# ============================================================
# HISTORICAL EDGE CONTAINER
# ============================================================

def create_edge_record():
    return {
        "index": "",
        "timeframe": "",
        "regime": "",
        "direction": "",
        "entry_style": "",
        "combination": "",

        "rr": 0.0,
        "hold": 0,

        "signals": 0,
        "triggered": 0,
        "trigger_pct": 0.0,

        "wins": 0,
        "losses": 0,
        "mtm": 0,
        "not_triggered": 0,

        "win_rate": 0.0,
        "expectancy": 0.0,
        "profit_factor": 0.0,
        "net_r": 0.0,

        "drawdown_r": 0.0,
        "max_consecutive_losses": 0,

        "historical_score": 0.0,
    }


# ============================================================
# METRIC EXTRACTION
# ============================================================

def get_metric(
    data,
    possible_keys,
    default=0.0,
):
    if not isinstance(
        data,
        dict,
    ):
        return default

    for key in possible_keys:

        if key in data:
            return data[key]

    return default


def extract_edge_record(
    key,
    stats,
    index_name="COMBINED",
):
    """
    Converts historical trade-style result into one
    normalized AI edge record.

    Designed to tolerate small naming differences between
    research versions.
    """

    record = create_edge_record()

    record["index"] = index_name

    # --------------------------------------------------------
    # READ KEY
    # --------------------------------------------------------

    if isinstance(
        key,
        tuple,
    ):

        parts = list(key)

        if len(parts) > 0:
            record["timeframe"] = normalize_timeframe(
                parts[0]
            )

        if len(parts) > 1:
            record["regime"] = str(
                parts[1]
            )

        if len(parts) > 2:
            record["combination"] = str(
                parts[2]
            )

        if len(parts) > 3:
            record["direction"] = normalize_direction(
                parts[3]
            )

        if len(parts) > 4:
            record["rr"] = safe_float(
                parts[4]
            )

        if len(parts) > 5:
            record["hold"] = safe_int(
                parts[5]
            )

        if len(parts) > 6:
            record["entry_style"] = (
                normalize_entry_style(
                    parts[6]
                )
            )

    # --------------------------------------------------------
    # READ STATS
    # --------------------------------------------------------

    if isinstance(
        stats,
        dict,
    ):

        timeframe = get_metric(
            stats,
            (
                "timeframe",
                "tf",
            ),
            record["timeframe"],
        )

        regime = get_metric(
            stats,
            (
                "regime",
                "market_regime",
            ),
            record["regime"],
        )

        direction = get_metric(
            stats,
            (
                "direction",
                "side",
                "signal_direction",
            ),
            record["direction"],
        )

        combination = get_metric(
            stats,
            (
                "combination",
                "combo",
                "setup",
            ),
            record["combination"],
        )

        entry_style = get_metric(
            stats,
            (
                "entry_style",
                "trade_style",
                "style",
            ),
            record["entry_style"],
        )

        record["timeframe"] = normalize_timeframe(
            timeframe
        )

        record["regime"] = str(
            regime
        )

        record["direction"] = normalize_direction(
            direction
        )

        record["combination"] = str(
            combination
        )

        record["entry_style"] = (
            normalize_entry_style(
                entry_style
            )
        )

        record["rr"] = safe_float(
            get_metric(
                stats,
                (
                    "rr",
                    "risk_reward",
                ),
                record["rr"],
            )
        )

        record["hold"] = safe_int(
            get_metric(
                stats,
                (
                    "hold",
                    "hold_candles",
                ),
                record["hold"],
            )
        )

        record["signals"] = safe_int(
            get_metric(
                stats,
                (
                    "signals",
                    "signal_count",
                    "total_signals",
                    "sig",
                    "trades",
                    "n",
                ),
                0,
            )
        )

        record["triggered"] = safe_int(
            get_metric(
                stats,
                (
                    "triggered",
                    "trigger_count",
                    "trg",
                ),
                record["signals"],
            )
        )

        record["trigger_pct"] = safe_float(
            get_metric(
                stats,
                (
                    "trigger_pct",
                    "triggered_pct",
                    "trg_pct",
                ),
                0.0,
            )
        )

        record["wins"] = safe_int(
            get_metric(
                stats,
                (
                    "wins",
                    "win",
                    "w",
                ),
                0,
            )
        )

        record["losses"] = safe_int(
            get_metric(
                stats,
                (
                    "losses",
                    "loss",
                    "l",
                ),
                0,
            )
        )

        record["mtm"] = safe_int(
            get_metric(
                stats,
                (
                    "mtm",
                    "mark_to_market",
                    "noexit",
                ),
                0,
            )
        )

        record["not_triggered"] = safe_int(
            get_metric(
                stats,
                (
                    "not_triggered",
                    "nt",
                ),
                0,
            )
        )

        record["win_rate"] = safe_float(
            get_metric(
                stats,
                (
                    "win_rate",
                    "win_pct",
                    "winrate",
                ),
                0.0,
            )
        )

        record["expectancy"] = safe_float(
            get_metric(
                stats,
                (
                    "expectancy",
                    "exp",
                    "expectancy_r",
                ),
                0.0,
            )
        )

        record["profit_factor"] = safe_float(
            get_metric(
                stats,
                (
                    "profit_factor",
                    "pf",
                ),
                0.0,
            )
        )

        record["net_r"] = safe_float(
            get_metric(
                stats,
                (
                    "net_r",
                    "net",
                    "total_r",
                ),
                0.0,
            )
        )

        record["drawdown_r"] = safe_float(
            get_metric(
                stats,
                (
                    "drawdown_r",
                    "max_drawdown",
                    "dd",
                    "dd_r",
                ),
                0.0,
            )
        )

        record[
            "max_consecutive_losses"
        ] = safe_int(
            get_metric(
                stats,
                (
                    "max_consecutive_losses",
                    "max_losses",
                    "maxl",
                ),
                0,
            )
        )

    # --------------------------------------------------------
    # DERIVE MISSING METRICS
    # --------------------------------------------------------

    if (
        record["trigger_pct"] <= 0.0
        and record["signals"] > 0
    ):
        record["trigger_pct"] = (
            record["triggered"]
            / record["signals"]
            * 100.0
        )

    resolved = (
        record["wins"]
        + record["losses"]
    )

    if (
        record["win_rate"] <= 0.0
        and resolved > 0
    ):
        record["win_rate"] = (
            record["wins"]
            / resolved
            * 100.0
        )

    return record


# ============================================================
# HISTORICAL EDGE SCORE
# ============================================================

def calculate_historical_score(
    record,
):
    """
    Score range:
    approximately 0 to 100.

    This is NOT machine-learning probability.
    It is a weighted historical quality score.
    """

    win_rate = safe_float(
        record.get(
            "win_rate"
        )
    )

    expectancy = safe_float(
        record.get(
            "expectancy"
        )
    )

    profit_factor = safe_float(
        record.get(
            "profit_factor"
        )
    )

    samples = safe_int(
        record.get(
            "triggered",
            record.get(
                "signals",
                0,
            ),
        )
    )

    drawdown = safe_float(
        record.get(
            "drawdown_r"
        )
    )

    max_losses = safe_int(
        record.get(
            "max_consecutive_losses"
        )
    )

    trigger_pct = safe_float(
        record.get(
            "trigger_pct"
        )
    )

    # Win rate:
    # 50% = 50 score
    # 75% = 100 score
    win_score = clamp(
        (
            win_rate
            - 50.0
        )
        * 2.0
        + 50.0,
        0.0,
        100.0,
    )

    # Expectancy:
    # +0.50R and above receives strong score.
    expectancy_score = clamp(
        expectancy
        / 0.50
        * 100.0,
        0.0,
        100.0,
    )

    # PF:
    # PF 1 = weak
    # PF 3 = strong
    pf_score = clamp(
        (
            profit_factor
            - 1.0
        )
        / 2.0
        * 100.0,
        0.0,
        100.0,
    )

    # Sample reliability.
    sample_score = clamp(
        samples
        / STRONG_SAMPLE_SIZE
        * 100.0,
        0.0,
        100.0,
    )

    # Lower drawdown = better.
    dd_score = clamp(
        100.0
        - (
            drawdown
            / DD_WARNING_R
            * 50.0
        ),
        0.0,
        100.0,
    )

    # Trigger reliability.
    trigger_score = clamp(
        trigger_pct,
        0.0,
        100.0,
    )

    score = (
        win_score * 0.25
        + expectancy_score * 0.25
        + pf_score * 0.20
        + sample_score * 0.10
        + dd_score * 0.10
        + trigger_score * 0.10
    )

    # Penalize very small samples.
    if samples < MIN_SAMPLE_SIZE:

        reliability = clamp(
            samples
            / MIN_SAMPLE_SIZE,
            0.25,
            1.0,
        )

        score *= reliability

    # Losing streak risk penalty.
    if max_losses >= 6:
        score -= 8.0

    elif max_losses >= 4:
        score -= 4.0

    return clamp(
        score,
        0.0,
        100.0,
    )


# ============================================================
# EDGE VALIDATION
# ============================================================

def is_qualified_edge(
    record,
):
    samples = max(
        safe_int(
            record.get(
                "triggered"
            )
        ),
        safe_int(
            record.get(
                "signals"
            )
        ),
    )

    if samples < MIN_SAMPLE_SIZE:
        return False

    if (
        safe_float(
            record.get(
                "win_rate"
            )
        )
        < MIN_WIN_RATE
    ):
        return False

    if (
        safe_float(
            record.get(
                "profit_factor"
            )
        )
        < MIN_PROFIT_FACTOR
    ):
        return False

    if (
        safe_float(
            record.get(
                "expectancy"
            )
        )
        <= MIN_EXPECTANCY
    ):
        return False

    return True


# ============================================================
# HISTORICAL EDGE DATABASE
# ============================================================

class HistoricalEdgeDatabase:

    def __init__(self):

        self.records = []

        self.by_timeframe = defaultdict(
            list
        )

        self.by_regime = defaultdict(
            list
        )

        self.by_direction = defaultdict(
            list
        )

        self.by_entry_style = defaultdict(
            list
        )

        self.by_exact_setup = defaultdict(
            list
        )


    def add_record(
        self,
        record,
    ):

        if not isinstance(
            record,
            dict,
        ):
            return

        record = dict(
            record
        )

        record[
            "historical_score"
        ] = calculate_historical_score(
            record
        )

        self.records.append(
            record
        )

        timeframe = normalize_timeframe(
            record.get(
                "timeframe"
            )
        )

        regime = str(
            record.get(
                "regime",
                "",
            )
        )

        direction = normalize_direction(
            record.get(
                "direction"
            )
        )

        entry_style = (
            normalize_entry_style(
                record.get(
                    "entry_style"
                )
            )
        )

        combination = str(
            record.get(
                "combination",
                "",
            )
        )

        self.by_timeframe[
            timeframe
        ].append(
            record
        )

        self.by_regime[
            regime
        ].append(
            record
        )

        self.by_direction[
            direction
        ].append(
            record
        )

        self.by_entry_style[
            entry_style
        ].append(
            record
        )

        exact_key = (
            timeframe,
            regime,
            direction,
            combination,
            entry_style,
        )

        self.by_exact_setup[
            exact_key
        ].append(
            record
        )


    def add_results(
        self,
        results,
        index_name="COMBINED",
    ):

        if not isinstance(
            results,
            dict,
        ):
            return

        for key, stats in results.items():

            try:

                record = extract_edge_record(
                    key,
                    stats,
                    index_name,
                )

                self.add_record(
                    record
                )

            except Exception:

                traceback.print_exc()


    def qualified_records(
        self,
    ):

        return [
            record
            for record in self.records
            if is_qualified_edge(
                record
            )
        ]


    def find_matches(
        self,
        timeframe=None,
        regime=None,
        direction=None,
        combination=None,
        entry_style=None,
    ):

        matches = self.records

        if timeframe:

            tf = normalize_timeframe(
                timeframe
            )

            matches = [
                r
                for r in matches
                if normalize_timeframe(
                    r.get(
                        "timeframe"
                    )
                )
                == tf
            ]

        if regime:

            matches = [
                r
                for r in matches
                if str(
                    r.get(
                        "regime"
                    )
                )
                == str(
                    regime
                )
            ]

        if direction:

            normalized_direction = (
                normalize_direction(
                    direction
                )
            )

            matches = [
                r
                for r in matches
                if normalize_direction(
                    r.get(
                        "direction"
                    )
                )
                == normalized_direction
            ]

        if combination:

            matches = [
                r
                for r in matches
                if str(
                    r.get(
                        "combination"
                    )
                )
                == str(
                    combination
                )
            ]

        if entry_style:

            normalized_style = (
                normalize_entry_style(
                    entry_style
                )
            )

            matches = [
                r
                for r in matches
                if normalize_entry_style(
                    r.get(
                        "entry_style"
                    )
                )
                == normalized_style
            ]

        matches.sort(
            key=lambda x: (
                safe_float(
                    x.get(
                        "historical_score"
                    )
                ),
                safe_float(
                    x.get(
                        "expectancy"
                    )
                ),
                safe_float(
                    x.get(
                        "profit_factor"
                    )
                ),
            ),
            reverse=True,
        )

        return matches


    def best_match(
        self,
        timeframe=None,
        regime=None,
        direction=None,
        combination=None,
        entry_style=None,
    ):

        matches = self.find_matches(
            timeframe=timeframe,
            regime=regime,
            direction=direction,
            combination=combination,
            entry_style=entry_style,
        )

        if not matches:
            return None

        return matches[0]


print(
    "FINAL AI DECISION ENGINE "
    "PART 1 LOADED"
)
# ============================================================
# FINAL AI DECISION ENGINE
# Part 2/4
#
# Previous-day context
# + timeframe agreement
# + regime / PA matching
# ============================================================


# ============================================================
# PREVIOUS DAY CONTEXT
# ============================================================

def build_previous_day_context(
    previous_day_candles,
):
    """
    previous_day_candles:
    list of candle dictionaries.

    Expected keys where available:
    open, high, low, close, volume

    Returns previous-day market context.
    """

    if not previous_day_candles:

        return {
            "valid": False,
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "range": 0.0,
            "change_pct": 0.0,
            "position_in_range": 0.5,
            "direction": "NEUTRAL",
            "structure": "UNKNOWN",
        }

    opens = []
    highs = []
    lows = []
    closes = []

    for candle in previous_day_candles:

        if not isinstance(
            candle,
            dict,
        ):
            continue

        o = safe_float(
            candle.get(
                "open"
            )
        )

        h = safe_float(
            candle.get(
                "high"
            )
        )

        l = safe_float(
            candle.get(
                "low"
            )
        )

        c = safe_float(
            candle.get(
                "close"
            )
        )

        if h <= 0 or l <= 0:
            continue

        opens.append(
            o
        )

        highs.append(
            h
        )

        lows.append(
            l
        )

        closes.append(
            c
        )

    if not closes:

        return {
            "valid": False,
            "direction": "NEUTRAL",
            "structure": "UNKNOWN",
        }

    day_open = opens[0]

    day_high = max(
        highs
    )

    day_low = min(
        lows
    )

    day_close = closes[-1]

    day_range = max(
        day_high - day_low,
        0.0,
    )

    if day_open > 0:

        change_pct = (
            day_close
            - day_open
        ) / day_open * 100.0

    else:

        change_pct = 0.0

    if day_range > 0:

        position_in_range = (
            day_close
            - day_low
        ) / day_range

    else:

        position_in_range = 0.5

    if (
        change_pct > 0
        and position_in_range >= 0.65
    ):

        direction = "BULLISH"
        structure = "STRONG_BULL_CLOSE"

    elif (
        change_pct < 0
        and position_in_range <= 0.35
    ):

        direction = "BEARISH"
        structure = "STRONG_BEAR_CLOSE"

    elif position_in_range >= 0.70:

        direction = "BULLISH"
        structure = "BULL_CLOSE"

    elif position_in_range <= 0.30:

        direction = "BEARISH"
        structure = "BEAR_CLOSE"

    else:

        direction = "NEUTRAL"
        structure = "MIXED_CLOSE"

    return {
        "valid": True,

        "open": day_open,
        "high": day_high,
        "low": day_low,
        "close": day_close,

        "range": day_range,

        "change_pct": change_pct,

        "position_in_range": (
            position_in_range
        ),

        "direction": direction,

        "structure": structure,
    }


# ============================================================
# CURRENT DAY OPEN CONTEXT
# ============================================================

def build_open_context(
    previous_context,
    current_open,
    current_price,
):
    current_open = safe_float(
        current_open
    )

    current_price = safe_float(
        current_price
    )

    previous_close = safe_float(
        previous_context.get(
            "close"
        )
    )

    previous_high = safe_float(
        previous_context.get(
            "high"
        )
    )

    previous_low = safe_float(
        previous_context.get(
            "low"
        )
    )

    gap_pct = 0.0

    if previous_close > 0:

        gap_pct = (
            current_open
            - previous_close
        ) / previous_close * 100.0

    if gap_pct >= 0.20:

        gap_type = "GAP_UP"

    elif gap_pct <= -0.20:

        gap_type = "GAP_DOWN"

    else:

        gap_type = "FLAT_OPEN"

    if current_price > previous_high:

        location = (
            "ABOVE_PREVIOUS_HIGH"
        )

    elif current_price < previous_low:

        location = (
            "BELOW_PREVIOUS_LOW"
        )

    else:

        location = (
            "INSIDE_PREVIOUS_RANGE"
        )

    return {
        "gap_pct": gap_pct,
        "gap_type": gap_type,
        "location": location,
    }


# ============================================================
# PREVIOUS-DAY ALIGNMENT SCORE
# ============================================================

def previous_day_alignment_score(
    signal_direction,
    previous_context,
    open_context=None,
):
    direction = normalize_direction(
        signal_direction
    )

    score = 50.0

    previous_direction = (
        normalize_direction(
            previous_context.get(
                "direction"
            )
        )
    )

    if (
        previous_direction
        == direction
    ):

        score += 15.0

    elif (
        previous_direction
        != "NEUTRAL"
        and direction
        != "NEUTRAL"
    ):

        score -= 10.0

    if open_context:

        gap_type = open_context.get(
            "gap_type"
        )

        location = open_context.get(
            "location"
        )

        if (
            direction == "BULLISH"
            and gap_type == "GAP_UP"
        ):

            score += 5.0

        elif (
            direction == "BEARISH"
            and gap_type == "GAP_DOWN"
        ):

            score += 5.0

        if (
            direction == "BULLISH"
            and location
            == "ABOVE_PREVIOUS_HIGH"
        ):

            score += 15.0

        elif (
            direction == "BEARISH"
            and location
            == "BELOW_PREVIOUS_LOW"
        ):

            score += 15.0

    return clamp(
        score,
        0.0,
        100.0,
    )


# ============================================================
# TIMEFRAME EDGE
# ============================================================

def get_timeframe_edge(
    edge_db,
    timeframe,
    regime,
    direction,
    combination=None,
):
    matches = edge_db.find_matches(
        timeframe=timeframe,
        regime=regime,
        direction=direction,
        combination=combination,
    )

    qualified = [
        record
        for record in matches
        if is_qualified_edge(
            record
        )
    ]

    if qualified:

        return qualified[0]

    if matches:

        return matches[0]

    return None


# ============================================================
# 5M + 15M AGREEMENT
# ============================================================

def calculate_timeframe_agreement(
    edge_5m,
    edge_15m,
    requested_direction,
):
    direction = normalize_direction(
        requested_direction
    )

    if (
        edge_5m is None
        and edge_15m is None
    ):

        return {
            "score": 0.0,
            "status": "NO_DATA",
        }

    if (
        edge_5m is None
        or edge_15m is None
    ):

        return {
            "score": 50.0,
            "status": "SINGLE_TIMEFRAME",
        }

    direction_5m = normalize_direction(
        edge_5m.get(
            "direction"
        )
    )

    direction_15m = normalize_direction(
        edge_15m.get(
            "direction"
        )
    )

    score_5m = safe_float(
        edge_5m.get(
            "historical_score"
        )
    )

    score_15m = safe_float(
        edge_15m.get(
            "historical_score"
        )
    )

    if (
        direction_5m
        == direction_15m
        == direction
    ):

        return {
            "score": clamp(
                (
                    score_5m
                    + score_15m
                )
                / 2.0
                + 15.0,
                0.0,
                100.0,
            ),

            "status": (
                "STRONG_AGREEMENT"
            ),
        }

    if (
        direction_5m
        == direction_15m
    ):

        return {
            "score": 65.0,
            "status": "AGREEMENT",
        }

    return {
        "score": 25.0,
        "status": "CONFLICT",
    }


# ============================================================
# PRICE ACTION MATCH SCORE
# ============================================================

def price_action_match_score(
    combination,
):
    combo = str(
        combination or ""
    ).upper()

    if "PA_SWING_BREAK" in combo:

        return 95.0

    if "PA_STRONG_CANDLE" in combo:

        return 85.0

    if "PA_STRUCTURE" in combo:

        return 80.0

    if "PA_REJECTION" in combo:

        return 75.0

    if "PA_" in combo:

        return 65.0

    return 40.0


# ============================================================
# REGIME MATCH SCORE
# ============================================================

def regime_match_score(
    regime,
    direction,
):
    regime = str(
        regime or ""
    ).upper()

    direction = normalize_direction(
        direction
    )

    if (
        "BULL_TREND" in regime
        and direction == "BULLISH"
    ):

        return 100.0

    if (
        "BEAR_TREND" in regime
        and direction == "BEARISH"
    ):

        return 100.0

    if (
        "BULL_MIXED" in regime
        and direction == "BULLISH"
    ):

        return 80.0

    if (
        "BEAR_MIXED" in regime
        and direction == "BEARISH"
    ):

        return 80.0

    if "SIDEWAYS" in regime:

        return 65.0

    return 40.0


# ============================================================
# ENTRY STYLE SELECTION
# ============================================================

def choose_best_entry_style(
    edge_db,
    timeframe,
    regime,
    direction,
    combination,
):
    around = edge_db.best_match(
        timeframe=timeframe,
        regime=regime,
        direction=direction,
        combination=combination,
        entry_style="BUY_AROUND",
    )

    above = edge_db.best_match(
        timeframe=timeframe,
        regime=regime,
        direction=direction,
        combination=combination,
        entry_style="BUY_ABOVE",
    )

    if (
        around is None
        and above is None
    ):

        return {
            "winner": "UNKNOWN",
            "record": None,
            "around": None,
            "above": None,
        }

    if around is None:

        return {
            "winner": "BUY_ABOVE",
            "record": above,
            "around": None,
            "above": above,
        }

    if above is None:

        return {
            "winner": "BUY_AROUND",
            "record": around,
            "around": around,
            "above": None,
        }

    around_score = safe_float(
        around.get(
            "historical_score"
        )
    )

    above_score = safe_float(
        above.get(
            "historical_score"
        )
    )

    if above_score > around_score:

        winner = "BUY_ABOVE"
        record = above

    else:

        winner = "BUY_AROUND"
        record = around

    return {
        "winner": winner,
        "record": record,
        "around": around,
        "above": above,
    }


# ============================================================
# EARLY MARKET MODE
# ============================================================

def determine_market_phase(
    current_time=None,
):
    if current_time is None:

        current_time = (
            datetime.now().time()
        )

    minutes = (
        current_time.hour
        * 60
        + current_time.minute
    )

    market_open = (
        9 * 60
        + 15
    )

    first_5m_complete = (
        9 * 60
        + 20
    )

    first_15m_complete = (
        9 * 60
        + 30
    )

    if minutes < market_open:

        return "PRE_MARKET"

    if minutes < first_5m_complete:

        return "OPENING_5M_BUILDING"

    if minutes < first_15m_complete:

        return "EARLY_5M_MODE"

    return "FULL_5M_15M_MODE"


# ============================================================
# TIMEFRAME WEIGHTS BY MARKET PHASE
# ============================================================

def get_dynamic_timeframe_weights(
    market_phase,
):
    if market_phase == "EARLY_5M_MODE":

        return {
            "5M": 0.70,
            "15M": 0.00,
            "PREVIOUS_DAY": 0.30,
        }

    if (
        market_phase
        == "FULL_5M_15M_MODE"
    ):

        return {
            "5M": 0.40,
            "15M": 0.45,
            "PREVIOUS_DAY": 0.15,
        }

    return {
        "5M": 0.0,
        "15M": 0.0,
        "PREVIOUS_DAY": 1.0,
    }


print(
    "FINAL AI DECISION ENGINE "
    "PART 2 LOADED"
)
# ============================================================
# FINAL AI DECISION ENGINE
# Part 3/4
#
# Final scoring and AI-style decision layer
# ============================================================


# ============================================================
# EDGE QUALITY
# ============================================================

def edge_quality_score(
    edge,
):
    if edge is None:
        return 0.0

    return safe_float(
        edge.get(
            "historical_score"
        )
    )


# ============================================================
# FINAL DECISION SCORE
# ============================================================

def calculate_final_decision_score(
    primary_edge,
    edge_5m,
    edge_15m,
    regime,
    direction,
    combination,
    previous_context,
    open_context,
    market_phase,
):
    historical_score = (
        edge_quality_score(
            primary_edge
        )
    )

    tf_agreement = (
        calculate_timeframe_agreement(
            edge_5m,
            edge_15m,
            direction,
        )
    )

    regime_score = (
        regime_match_score(
            regime,
            direction,
        )
    )

    pa_score = (
        price_action_match_score(
            combination
        )
    )

    previous_score = (
        previous_day_alignment_score(
            direction,
            previous_context,
            open_context,
        )
    )

    weights = (
        get_dynamic_timeframe_weights(
            market_phase
        )
    )

    score_5m = edge_quality_score(
        edge_5m
    )

    score_15m = edge_quality_score(
        edge_15m
    )

    timeframe_score = (
        score_5m
        * weights.get(
            "5M",
            0.0,
        )
        + score_15m
        * weights.get(
            "15M",
            0.0,
        )
        + previous_score
        * weights.get(
            "PREVIOUS_DAY",
            0.0,
        )
    )

    final_score = (
        historical_score * 0.40
        + timeframe_score * 0.25
        + tf_agreement[
            "score"
        ] * 0.15
        + regime_score * 0.08
        + pa_score * 0.07
        + previous_score * 0.05
    )

    return {
        "final_score": clamp(
            final_score,
            0.0,
            100.0,
        ),

        "historical_score": (
            historical_score
        ),

        "timeframe_score": (
            timeframe_score
        ),

        "timeframe_agreement": (
            tf_agreement
        ),

        "regime_score": (
            regime_score
        ),

        "price_action_score": (
            pa_score
        ),

        "previous_day_score": (
            previous_score
        ),
    }


# ============================================================
# CONFIDENCE CLASSIFICATION
# ============================================================

def classify_confidence(
    score,
):
    score = safe_float(
        score
    )

    if (
        score
        >= HIGH_CONFIDENCE_SCORE
    ):

        return "HIGH"

    if (
        score
        >= MEDIUM_CONFIDENCE_SCORE
    ):

        return "MEDIUM"

    return "LOW"


# ============================================================
# TRADE ACTION
# ============================================================

def determine_trade_action(
    final_score,
    direction,
    agreement_status,
):
    direction = normalize_direction(
        direction
    )

    if (
        agreement_status
        == "CONFLICT"
        and final_score
        < HIGH_CONFIDENCE_SCORE
    ):

        return "WAIT"

    if (
        final_score
        < MEDIUM_CONFIDENCE_SCORE
    ):

        return "WAIT"

    if direction == "BULLISH":

        return "CE"

    if direction == "BEARISH":

        return "PE"

    return "WAIT"


# ============================================================
# FINAL AI DECISION
# ============================================================

def make_ai_decision(
    edge_db,
    regime,
    direction,
    combination,
    previous_day_candles=None,
    current_open=0.0,
    current_price=0.0,
    current_time=None,
):
    direction = normalize_direction(
        direction
    )

    market_phase = (
        determine_market_phase(
            current_time
        )
    )

    previous_context = (
        build_previous_day_context(
            previous_day_candles
            or []
        )
    )

    open_context = (
        build_open_context(
            previous_context,
            current_open,
            current_price,
        )
    )

    # --------------------------------------------------------
    # 5M HISTORICAL EDGE
    # --------------------------------------------------------

    edge_5m = (
        get_timeframe_edge(
            edge_db,
            "5M",
            regime,
            direction,
            combination,
        )
    )

    # --------------------------------------------------------
    # 15M HISTORICAL EDGE
    # --------------------------------------------------------

    edge_15m = (
        get_timeframe_edge(
            edge_db,
            "15M",
            regime,
            direction,
            combination,
        )
    )

    # --------------------------------------------------------
    # COMBINED 5M+15M EDGE
    # --------------------------------------------------------

    edge_combined = (
        get_timeframe_edge(
            edge_db,
            "5M+15M",
            regime,
            direction,
            combination,
        )
    )

    # --------------------------------------------------------
    # SELECT PRIMARY TIMEFRAME
    # --------------------------------------------------------

    if (
        market_phase
        == "EARLY_5M_MODE"
    ):

        # Prefer 5M edge in early market.
        # If no exact 5M edge exists but the live setup
        # has a valid combined historical edge, use it.
        if edge_5m is not None:
            primary_edge = edge_5m
            primary_timeframe = "5M"

        elif edge_combined is not None:
            primary_edge = edge_combined
            primary_timeframe = "5M+15M"

        elif edge_15m is not None:
            primary_edge = edge_15m
            primary_timeframe = "15M"

        else:
            primary_edge = None
            primary_timeframe = "UNKNOWN"

    else:

        candidates = [
            edge
            for edge in (
                edge_5m,
                edge_15m,
                edge_combined,
            )
            if edge is not None
        ]

        if candidates:

            candidates.sort(
                key=lambda x: (
                    edge_quality_score(
                        x
                    ),
                    safe_float(
                        x.get(
                            "expectancy"
                        )
                    ),
                ),
                reverse=True,
            )

            primary_edge = (
                candidates[0]
            )

            primary_timeframe = (
                primary_edge.get(
                    "timeframe",
                    "UNKNOWN",
                )
            )

        else:

            primary_edge = None
            primary_timeframe = (
                "UNKNOWN"
            )

    # --------------------------------------------------------
    # ENTRY STYLE
    # --------------------------------------------------------

    entry_selection = (
        choose_best_entry_style(
            edge_db,
            primary_timeframe,
            regime,
            direction,
            combination,
        )
    )

    if (
        entry_selection[
            "record"
        ]
        is not None
    ):

        primary_edge = (
            entry_selection[
                "record"
            ]
        )

    entry_style = (
        entry_selection[
            "winner"
        ]
    )

    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------

    scores = (
        calculate_final_decision_score(
            primary_edge,
            edge_5m,
            edge_15m,
            regime,
            direction,
            combination,
            previous_context,
            open_context,
            market_phase,
        )
    )

    final_score = (
        scores[
            "final_score"
        ]
    )

    confidence = (
        classify_confidence(
            final_score
        )
    )

    agreement_status = (
        scores[
            "timeframe_agreement"
        ][
            "status"
        ]
    )

    action = (
        determine_trade_action(
            final_score,
            direction,
            agreement_status,
        )
    )

    # --------------------------------------------------------
    # RR + HOLD
    # --------------------------------------------------------

    rr = 0.0
    hold = 0

    historical_win = 0.0
    historical_pf = 0.0
    historical_exp = 0.0
    historical_dd = 0.0
    historical_samples = 0

    if primary_edge:

        rr = safe_float(
            primary_edge.get(
                "rr"
            )
        )

        hold = safe_int(
            primary_edge.get(
                "hold"
            )
        )

        historical_win = safe_float(
            primary_edge.get(
                "win_rate"
            )
        )

        historical_pf = safe_float(
            primary_edge.get(
                "profit_factor"
            )
        )

        historical_exp = safe_float(
            primary_edge.get(
                "expectancy"
            )
        )

        historical_dd = safe_float(
            primary_edge.get(
                "drawdown_r"
            )
        )

        historical_samples = max(
            safe_int(
                primary_edge.get(
                    "triggered"
                )
            ),
            safe_int(
                primary_edge.get(
                    "signals"
                )
            ),
        )

    # --------------------------------------------------------
    # SIGNAL TYPE
    # --------------------------------------------------------

    if (
        market_phase
        == "EARLY_5M_MODE"
    ):

        signal_type = (
            "EARLY_5M_SIGNAL"
        )

    elif (
        market_phase
        == "FULL_5M_15M_MODE"
    ):

        signal_type = (
            "5M_15M_CONFIRMED"
        )

    else:

        signal_type = (
            "NO_LIVE_SIGNAL"
        )

    return {
        "timestamp": (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ),

        "market_phase": (
            market_phase
        ),

        "signal_type": (
            signal_type
        ),

        "regime": regime,

        "direction": direction,

        "action": action,

        "combination": combination,

        "primary_timeframe": (
            primary_timeframe
        ),

        "entry_style": (
            entry_style
        ),

        "rr": rr,

        "hold": hold,

        "confidence": (
            confidence
        ),

        "ai_score": (
            final_score
        ),

        "historical_win_rate": (
            historical_win
        ),

        "historical_pf": (
            historical_pf
        ),

        "historical_expectancy": (
            historical_exp
        ),

        "historical_drawdown": (
            historical_dd
        ),

        "historical_samples": (
            historical_samples
        ),

        "edge_5m": edge_5m,

        "edge_15m": edge_15m,

        "edge_5m15m": (
            edge_combined
        ),

        "previous_day": (
            previous_context
        ),

        "open_context": (
            open_context
        ),

        "score_details": (
            scores
        ),
    }


# ============================================================
# PRINT ONE AI DECISION
# ============================================================

def print_ai_decision(
    decision,
):
    print(
        "\n"
        + "=" * 100
    )

    print(
        "FINAL AI DECISION"
    )

    print(
        "=" * 100
    )

    print(
        "TIME:",
        decision.get(
            "timestamp"
        )
    )

    print(
        "MARKET PHASE:",
        decision.get(
            "market_phase"
        )
    )

    print(
        "SIGNAL TYPE:",
        decision.get(
            "signal_type"
        )
    )

    print(
        "REGIME:",
        decision.get(
            "regime"
        )
    )

    print(
        "DIRECTION:",
        decision.get(
            "direction"
        )
    )

    print(
        "ACTION:",
        decision.get(
            "action"
        )
    )

    print(
        "TIMEFRAME:",
        decision.get(
            "primary_timeframe"
        )
    )

    print(
        "ENTRY:",
        decision.get(
            "entry_style"
        )
    )

    print(
        "SETUP:",
        decision.get(
            "combination"
        )
    )

    print(
        "RR:",
        decision.get(
            "rr"
        )
    )

    print(
        "HOLD:",
        decision.get(
            "hold"
        )
    )

    print(
        "AI SCORE:",
        f"{decision.get('ai_score', 0):.2f}",
    )

    print(
        "CONFIDENCE:",
        decision.get(
            "confidence"
        )
    )

    print(
        "HIST WIN:",
        f"{decision.get('historical_win_rate', 0):.2f}%",
    )

    print(
        "PF:",
        f"{decision.get('historical_pf', 0):.2f}",
    )

    print(
        "EXP:",
        f"{decision.get('historical_expectancy', 0):+.3f}R",
    )

    print(
        "DD:",
        f"{decision.get('historical_drawdown', 0):.2f}R",
    )

    print(
        "SAMPLES:",
        decision.get(
            "historical_samples"
        )
    )

    agreement = (
        decision
        .get(
            "score_details",
            {},
        )
        .get(
            "timeframe_agreement",
            {},
        )
    )

    print(
        "5M/15M:",
        agreement.get(
            "status",
            "UNKNOWN",
        )
    )

    print(
        "=" * 100
    )


print(
    "FINAL AI DECISION ENGINE "
    "PART 3 LOADED"
)
# ============================================================
# FINAL AI DECISION ENGINE
# Part 4/4
#
# Historical backtest integration
# + engine build
# + summary
# + main
# ============================================================


# ============================================================
# LOAD HISTORICAL AI EDGE CACHE
# ============================================================

AI_EDGE_CACHE_FILE = os.path.join(
    CURRENT_DIR,
    "ai_edge_cache.json",
)


def load_ai_edge_cache(
    cache_file=AI_EDGE_CACHE_FILE,
):
    """
    Load precomputed historical AI edge records from JSON.

    This avoids running historical research inside the
    live trading bot.
    """
    if not os.path.exists(cache_file):
        raise FileNotFoundError(
            f"AI edge cache not found: {cache_file}"
        )

    with open(
        cache_file,
        "r",
        encoding="utf-8",
    ) as f:
        records = json.load(f)

    if not isinstance(records, list):
        raise ValueError(
            "AI edge cache must contain a list of records"
        )

    edge_db = HistoricalEdgeDatabase()

    loaded = 0

    for record in records:
        if not isinstance(record, dict):
            continue

        edge_db.add_record(record)
        loaded += 1

    if loaded == 0:
        raise ValueError(
            "AI edge cache contains no valid records"
        )

    return edge_db


# ============================================================
# BUILD HISTORICAL DATABASE
# ============================================================

def build_historical_edge_database(
    combined_results,
):
    edge_db = HistoricalEdgeDatabase()

    enriched_results = {}

    for key, stats in combined_results.items():
        if not isinstance(stats, dict):
            continue

        enriched = dict(stats)

        metrics = trade_research.calculate_trade_metrics(
            stats
        )

        if metrics:
            enriched.update(metrics)
            enriched["signals"] = metrics["total"]
            enriched["triggered"] = metrics["total"]

        enriched_results[key] = enriched

    edge_db.add_results(
        enriched_results,
        index_name="NIFTY+SENSEX",
    )

    return edge_db


# ============================================================
# DATABASE SUMMARY
# ============================================================

def print_database_summary(
    edge_db,
):
    print(
        "\n"
        + "=" * 100
    )

    print(
        "FINAL AI HISTORICAL "
        "EDGE DATABASE"
    )

    print(
        "=" * 100
    )

    print(
        "TOTAL RECORDS:",
        len(
            edge_db.records
        ),
    )

    qualified = (
        edge_db.qualified_records()
    )

    print(
        "QUALIFIED EDGES:",
        len(
            qualified
        ),
    )

    for timeframe in (
        "5M",
        "15M",
        "5M+15M",
    ):

        records = (
            edge_db.by_timeframe[
                timeframe
            ]
        )

        qualified_tf = [
            record
            for record in records
            if is_qualified_edge(
                record
            )
        ]

        print(
            timeframe,
            "| TOTAL",
            len(
                records
            ),
            "| QUALIFIED",
            len(
                qualified_tf
            ),
        )

    print(
        "=" * 100
    )


# ============================================================
# PRINT TOP HISTORICAL EDGES
# ============================================================

def print_top_ai_edges(
    edge_db,
    limit=30,
):
    records = (
        edge_db.qualified_records()
    )

    records.sort(
        key=lambda x: (
            safe_float(
                x.get(
                    "historical_score"
                )
            ),
            safe_float(
                x.get(
                    "expectancy"
                )
            ),
            safe_float(
                x.get(
                    "profit_factor"
                )
            ),
        ),
        reverse=True,
    )

    print(
        "\n"
        + "=" * 180
    )

    print(
        "TOP FINAL AI "
        "HISTORICAL EDGES"
    )

    print(
        "=" * 180
    )

    if not records:

        print(
            "NO QUALIFIED "
            "HISTORICAL EDGES"
        )

        return

    for record in records[
        :limit
    ]:

        print(
            f"{record.get('timeframe', ''):<7}"
            f" | {record.get('regime', ''):<12}"
            f" | {record.get('direction', ''):<7}"
            f" | {record.get('entry_style', ''):<10}"
            f" | SCORE {record.get('historical_score', 0):6.2f}"
            f" | WIN {record.get('win_rate', 0):6.2f}%"
            f" | EXP {record.get('expectancy', 0):+.3f}R"
            f" | PF {record.get('profit_factor', 0):5.2f}"
            f" | DD {record.get('drawdown_r', 0):5.2f}R"
            f" | N {max(record.get('triggered', 0), record.get('signals', 0)):<4}"
            f" | RR 1:{record.get('rr', 0)}"
            f" | HOLD {record.get('hold', 0)}"
            f" | {record.get('combination', '')}"
        )


# ============================================================
# RUN EXISTING ADVANCED TRADE RESEARCH
# ============================================================

def run_historical_research():
    """
    Uses existing trade_style_backtest research engine.

    NIFTY and SENSEX are researched separately,
    then merged exactly through the existing
    merge_trade_results function.
    """

    api = (
        trade_research.load_api()
    )

    combined_results = defaultdict(
        trade_research.create_trade_stats
    )

    for index_name in INDEXES:

        print(
            "\n"
            + "=" * 100
        )

        print(
            "AI HISTORICAL RESEARCH:",
            index_name,
        )

        print(
            "=" * 100
        )

        try:

            results = (
                trade_research
                .research_index(
                    api,
                    index_name,
                )
            )

            trade_research.merge_trade_results(
                combined_results,
                results,
            )

        except Exception as error:

            print(
                "\nERROR",
                index_name,
                type(
                    error
                ).__name__,
                error,
            )

            traceback.print_exc()

    return combined_results


# ============================================================
# SAMPLE DECISION TEST
# ============================================================

def run_sample_decision(
    edge_db,
):
    """
    This only verifies that the AI decision layer runs.

    Live bot integration later will replace these sample
    inputs with actual current candles and regime.
    """

    qualified = (
        edge_db.qualified_records()
    )

    if not qualified:

        print(
            "\nNO QUALIFIED EDGE "
            "FOR SAMPLE AI DECISION"
        )

        return

    qualified.sort(
        key=lambda x: (
            safe_float(
                x.get(
                    "historical_score"
                )
            ),
            safe_float(
                x.get(
                    "expectancy"
                )
            ),
        ),
        reverse=True,
    )

    best = qualified[0]

    regime = best.get(
        "regime"
    )

    direction = best.get(
        "direction"
    )

    combination = best.get(
        "combination"
    )

    # Dummy previous-day candles are intentionally
    # not fabricated here.
    #
    # Empty list means previous-day component remains
    # neutral during this structural engine test.

    decision = make_ai_decision(
        edge_db=edge_db,
        regime=regime,
        direction=direction,
        combination=combination,
        previous_day_candles=[],
        current_open=0.0,
        current_price=0.0,
    )

    print_ai_decision(
        decision
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n"
        + "=" * 100
    )

    print(
        "FINAL AI DECISION ENGINE"
    )

    print(
        "5M + 15M + REGIME "
        "+ PRICE ACTION "
        "+ PREVIOUS DAY "
        "+ ENTRY STYLE"
    )

    print(
        "=" * 100
    )

    # --------------------------------------------------------
    # STEP 1:
    # Run existing historical trade research.
    # --------------------------------------------------------

    combined_results = (
        run_historical_research()
    )

    if not combined_results:

        print(
            "\nNO HISTORICAL RESULTS"
        )

        return

    # --------------------------------------------------------
    # STEP 2:
    # Convert historical research into AI edge database.
    # --------------------------------------------------------

    edge_db = (
        build_historical_edge_database(
            combined_results
        )
    )

    # --------------------------------------------------------
    # STEP 3:
    # Print database health.
    # --------------------------------------------------------

    print_database_summary(
        edge_db
    )

    # --------------------------------------------------------
    # STEP 4:
    # Rank strongest historical edges.
    # --------------------------------------------------------

    print_top_ai_edges(
        edge_db,
        limit=30,
    )

    # --------------------------------------------------------
    # STEP 5:
    # Structural test of final decision layer.
    # --------------------------------------------------------

    run_sample_decision(
        edge_db
    )

    print(
        "\n"
        + "=" * 100
    )

    print(
        "FINAL AI DECISION "
        "ENGINE RESEARCH COMPLETE"
    )

    print(
        "=" * 100
    )


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\nSTOPPED BY USER"
        )

    except Exception as error:

        print(
            "\nFATAL ERROR:",
            type(
                error
            ).__name__,
            error,
        )

        traceback.print_exc()
