import sys
import os
import traceback
from collections import defaultdict

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY

from historical.multi_timeframe_research import (
    TOKEN_FILE,
    MAX_CANDLES,
    CONFIG,
    TIMEFRAMES,
    fetch_max_950,
)

from historical.indicator_combination_research import (
    prepare_candles,
    build_indicator_states,
    get_combinations,
    cross_timeframe_combinations,
    build_15m_state_map,
    get_15m_state_for_5m,
)

from historical.market_regime_combination_research import (
    detect_local_regime,
)

from historical.price_action_regime_research import (
    build_price_action_states,
    get_price_action_combinations,
)


# ============================================================
# ENTRY STYLE BACKTEST
#
# COMPARES:
#   BUY_AROUND
#   BUY_ABOVE
#
# BULLISH:
#   BUY_AROUND = signal candle close
#   BUY_ABOVE  = signal candle high breakout
#
# BEARISH:
#   BUY_AROUND = signal candle close
#   BUY_ABOVE  = signal candle low breakdown
#
# BUY ABOVE:
#   Entry only after breakout/breakdown trigger.
#   If trigger never happens within HOLD window:
#   NOT_TRIGGERED
#
# STOP LOSS:
#   Bullish = signal candle low
#   Bearish = signal candle high
#
# RR:
#   1:1
#   1:1.5
#   1:2
#
# HOLD:
#   3 candles
#   5 candles
#
# METRICS:
#   Trigger Rate
#   Win Rate
#   Expectancy
#   Profit Factor
#   Net R
#   Max Drawdown
#   Max Consecutive Losses
#
# RESEARCH ONLY
# ============================================================

MIN_SAMPLE_SIZE = 20

RR_VALUES = [
    1.0,
    1.5,
    2.0,
]

MAX_HOLD_WINDOWS = [
    3,
    5,
]

ENTRY_STYLES = [
    "BUY_AROUND",
    "BUY_ABOVE",
]

RESEARCH_TIMEFRAMES = [
    "5M",
    "15M",
]


def safe_float(
    value,
    default=0.0
):
    try:
        return float(value)
    except Exception:
        return default


def create_stats():
    return {
        "signals": 0,
        "triggered": 0,
        "not_triggered": 0,
        "wins": 0,
        "losses": 0,
        "flat": 0,
        "target_hits": 0,
        "sl_hits": 0,
        "mtm_exits": 0,
        "net_r": 0.0,
        "gross_profit_r": 0.0,
        "gross_loss_r": 0.0,
        "returns": [],
    }


def get_entry_levels(
    candle,
    signal,
    entry_style,
    rr
):
    close = safe_float(
        candle["close"]
    )

    high = safe_float(
        candle["high"]
    )

    low = safe_float(
        candle["low"]
    )

    if close <= 0:
        return None

    if signal == "BULLISH":

        stop_loss = low

        if entry_style == "BUY_AROUND":
            entry = close
        else:
            entry = high

        risk = (
            entry - stop_loss
        )

        if risk <= 0:
            return None

        target = (
            entry + risk * rr
        )

    elif signal == "BEARISH":

        stop_loss = high

        if entry_style == "BUY_AROUND":
            entry = close
        else:
            entry = low

        risk = (
            stop_loss - entry
        )

        if risk <= 0:
            return None

        target = (
            entry - risk * rr
        )

    else:
        return None

    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "risk": risk,
    }


def simulate_entry_trade(
    candles,
    signal_index,
    signal,
    entry_style,
    rr,
    max_hold
):
    levels = get_entry_levels(
        candles[signal_index],
        signal,
        entry_style,
        rr
    )

    if levels is None:
        return None

    entry = levels["entry"]
    stop_loss = levels["stop_loss"]
    target = levels["target"]
    risk = levels["risk"]

    start_index = (
        signal_index + 1
    )

    end_index = min(
        len(candles),
        start_index + max_hold
    )

    if start_index >= len(candles):
        return None

    triggered = (
        entry_style == "BUY_AROUND"
    )

    trigger_index = start_index

    if entry_style == "BUY_ABOVE":

        triggered = False

        for i in range(
            start_index,
            end_index
        ):

            high = safe_float(
                candles[i]["high"]
            )

            low = safe_float(
                candles[i]["low"]
            )

            if signal == "BULLISH":

                if high >= entry:
                    triggered = True
                    trigger_index = i
                    break

            else:

                if low <= entry:
                    triggered = True
                    trigger_index = i
                    break

        if not triggered:

            return {
                "status": "NOT_TRIGGERED",
                "type": None,
                "r": 0.0,
            }

    for i in range(
        trigger_index,
        end_index
    ):

        high = safe_float(
            candles[i]["high"]
        )

        low = safe_float(
            candles[i]["low"]
        )

        if signal == "BULLISH":

            sl_hit = (
                low <= stop_loss
            )

            target_hit = (
                high >= target
            )

        else:

            sl_hit = (
                high >= stop_loss
            )

            target_hit = (
                low <= target
            )

        if sl_hit and target_hit:

            return {
                "status": "TRIGGERED",
                "type": "SL",
                "r": -1.0,
            }

        if sl_hit:

            return {
                "status": "TRIGGERED",
                "type": "SL",
                "r": -1.0,
            }

        if target_hit:

            return {
                "status": "TRIGGERED",
                "type": "TARGET",
                "r": rr,
            }

    final_close = safe_float(
        candles[
            end_index - 1
        ]["close"]
    )

    if signal == "BULLISH":

        mtm_r = (
            final_close - entry
        ) / risk

    else:

        mtm_r = (
            entry - final_close
        ) / risk

    mtm_r = max(
        -1.0,
        min(
            rr,
            mtm_r
        )
    )

    return {
        "status": "TRIGGERED",
        "type": "MTM",
        "r": mtm_r,
    }


def update_stats(
    stats,
    result
):
    stats["signals"] += 1

    if result is None:
        stats[
            "not_triggered"
        ] += 1
        return

    if (
        result["status"]
        == "NOT_TRIGGERED"
    ):

        stats[
            "not_triggered"
        ] += 1

        return

    stats["triggered"] += 1

    trade_r = result["r"]

    stats[
        "returns"
    ].append(
        trade_r
    )

    stats["net_r"] += trade_r

    if trade_r > 0:

        stats["wins"] += 1

        stats[
            "gross_profit_r"
        ] += trade_r

    elif trade_r < 0:

        stats["losses"] += 1

        stats[
            "gross_loss_r"
        ] += abs(
            trade_r
        )

    else:

        stats["flat"] += 1

    if result["type"] == "TARGET":

        stats[
            "target_hits"
        ] += 1

    elif result["type"] == "SL":

        stats[
            "sl_hits"
        ] += 1

    elif result["type"] == "MTM":

        stats[
            "mtm_exits"
        ] += 1
def research_timeframe(
    candles,
    indicator_states,
    price_action_states,
    timeframe
):
    results = defaultdict(
        create_stats
    )

    for i in range(
        len(candles)
    ):

        regime = detect_local_regime(
            candles,
            i
        )

        if regime == "UNKNOWN":
            continue

        indicator_combinations = (
            get_combinations(
                indicator_states[i]
            )
        )

        combinations = (
            get_price_action_combinations(
                indicator_combinations,
                price_action_states[i]
            )
        )

        for (
            combination,
            signal
        ) in combinations.items():

            if signal not in (
                "BULLISH",
                "BEARISH",
            ):
                continue

            for entry_style in (
                ENTRY_STYLES
            ):

                for rr in RR_VALUES:

                    for max_hold in (
                        MAX_HOLD_WINDOWS
                    ):

                        result = (
                            simulate_entry_trade(
                                candles,
                                i,
                                signal,
                                entry_style,
                                rr,
                                max_hold
                            )
                        )

                        key = (
                            timeframe,
                            regime,
                            combination,
                            signal,
                            entry_style,
                            rr,
                            max_hold,
                        )

                        update_stats(
                            results[key],
                            result
                        )

    return results


def research_cross_timeframe(
    candles_5m,
    states_5m,
    price_action_5m,
    candles_15m,
    states_15m
):
    results = defaultdict(
        create_stats
    )

    state_map_15m = (
        build_15m_state_map(
            candles_15m,
            states_15m
        )
    )

    for i in range(
        len(candles_5m)
    ):

        state_15m = (
            get_15m_state_for_5m(
                candles_5m[i],
                state_map_15m
            )
        )

        if state_15m is None:
            continue

        regime = detect_local_regime(
            candles_5m,
            i
        )

        if regime == "UNKNOWN":
            continue

        indicator_combinations = (
            cross_timeframe_combinations(
                states_5m[i],
                state_15m
            )
        )

        combinations = (
            get_price_action_combinations(
                indicator_combinations,
                price_action_5m[i]
            )
        )

        for (
            combination,
            signal
        ) in combinations.items():

            if signal not in (
                "BULLISH",
                "BEARISH",
            ):
                continue

            for entry_style in (
                ENTRY_STYLES
            ):

                for rr in RR_VALUES:

                    for max_hold in (
                        MAX_HOLD_WINDOWS
                    ):

                        result = (
                            simulate_entry_trade(
                                candles_5m,
                                i,
                                signal,
                                entry_style,
                                rr,
                                max_hold
                            )
                        )

                        key = (
                            "5M+15M",
                            regime,
                            combination,
                            signal,
                            entry_style,
                            rr,
                            max_hold,
                        )

                        update_stats(
                            results[key],
                            result
                        )

    return results


def merge_results(
    target,
    source
):
    for key, stats in source.items():

        target_stats = target[key]

        for field in (
            "signals",
            "triggered",
            "not_triggered",
            "wins",
            "losses",
            "flat",
            "target_hits",
            "sl_hits",
            "mtm_exits",
        ):

            target_stats[field] += (
                stats[field]
            )

        for field in (
            "net_r",
            "gross_profit_r",
            "gross_loss_r",
        ):

            target_stats[field] += (
                stats[field]
            )

        target_stats[
            "returns"
        ].extend(
            stats["returns"]
        )


def max_drawdown(
    returns
):
    equity = 0.0
    peak = 0.0
    maximum = 0.0

    for value in returns:

        equity += value

        peak = max(
            peak,
            equity
        )

        maximum = max(
            maximum,
            peak - equity
        )

    return maximum


def max_consecutive_losses(
    returns
):
    current = 0
    maximum = 0

    for value in returns:

        if value < 0:

            current += 1

            maximum = max(
                maximum,
                current
            )

        else:

            current = 0

    return maximum


def calculate_metrics(
    stats
):
    signals = stats["signals"]
    triggered = stats["triggered"]

    if signals <= 0:
        return None

    if triggered <= 0:
        return None

    trigger_rate = (
        triggered / signals
    ) * 100.0

    win_rate = (
        stats["wins"]
        / triggered
    ) * 100.0

    expectancy = (
        stats["net_r"]
        / triggered
    )

    gross_profit = (
        stats[
            "gross_profit_r"
        ]
    )

    gross_loss = (
        stats[
            "gross_loss_r"
        ]
    )

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            / gross_loss
        )

    elif gross_profit > 0:

        profit_factor = 999.0

    else:

        profit_factor = 0.0

    return {
        "signals": signals,
        "triggered": triggered,
        "not_triggered":
            stats["not_triggered"],
        "trigger_rate":
            trigger_rate,
        "win_rate":
            win_rate,
        "expectancy":
            expectancy,
        "profit_factor":
            profit_factor,
        "net_r":
            stats["net_r"],
        "drawdown":
            max_drawdown(
                stats["returns"]
            ),
        "max_losses":
            max_consecutive_losses(
                stats["returns"]
            ),
        "target_hits":
            stats["target_hits"],
        "sl_hits":
            stats["sl_hits"],
        "mtm_exits":
            stats["mtm_exits"],
    }
def build_ranked_results(
    results
):
    ranked = []

    for key, stats in results.items():

        metrics = calculate_metrics(
            stats
        )

        if metrics is None:
            continue

        if (
            metrics["signals"]
            < MIN_SAMPLE_SIZE
        ):
            continue

        (
            timeframe,
            regime,
            combination,
            signal,
            entry_style,
            rr,
            max_hold,
        ) = key

        ranked.append(
            (
                metrics["expectancy"],
                metrics["profit_factor"],
                metrics["win_rate"],
                metrics["trigger_rate"],
                metrics["signals"],
                metrics["triggered"],
                timeframe,
                regime,
                combination,
                signal,
                entry_style,
                rr,
                max_hold,
                metrics["net_r"],
                metrics["drawdown"],
                metrics["max_losses"],
                metrics["target_hits"],
                metrics["sl_hits"],
                metrics["mtm_exits"],
                metrics["not_triggered"],
            )
        )

    ranked.sort(
        key=lambda x: (
            x[0],
            x[1],
            x[5],
        ),
        reverse=True
    )

    return ranked


def print_results(
    title,
    results,
    limit=40
):
    print(
        "\n"
        + "=" * 180
    )

    print(title)

    ranked = build_ranked_results(
        results
    )

    if not ranked:

        print(
            "NO QUALIFIED RESULTS"
        )

        return []

    for row in ranked[:limit]:

        (
            expectancy,
            pf,
            win_rate,
            trigger_rate,
            signals,
            triggered,
            timeframe,
            regime,
            combination,
            signal,
            entry_style,
            rr,
            hold,
            net_r,
            drawdown,
            max_losses,
            target_hits,
            sl_hits,
            mtm_exits,
            not_triggered,
        ) = row

        print(
            f"{timeframe:<7} | "
            f"{regime:<12} | "
            f"{signal:<7} | "
            f"{entry_style:<10} | "
            f"{combination:<55} | "
            f"RR 1:{rr:<3} | "
            f"HOLD {hold:<2} | "
            f"SIG {signals:<4} | "
            f"TRG {triggered:<4} | "
            f"TRG% {trigger_rate:6.2f} | "
            f"WIN {win_rate:6.2f}% | "
            f"EXP {expectancy:+.3f}R | "
            f"PF {pf:5.2f} | "
            f"NET {net_r:+.2f}R | "
            f"DD {drawdown:.2f}R | "
            f"MAXL {max_losses:<2} | "
            f"TGT {target_hits:<3} | "
            f"SL {sl_hits:<3} | "
            f"MTM {mtm_exits:<3} | "
            f"NT {not_triggered:<3}"
        )

    return ranked


def research_index(
    api,
    index_name
):
    print(
        "\n"
        + "#" * 180
    )

    print(
        "ENTRY STYLE BACKTEST:",
        index_name
    )

    index_results = defaultdict(
        create_stats
    )

    prepared = {}

    for timeframe in (
        RESEARCH_TIMEFRAMES
    ):

        tf = TIMEFRAMES[
            timeframe
        ]

        print(
            "\nFETCHING",
            index_name,
            timeframe
        )

        rows = fetch_max_950(
            api,
            CONFIG[index_name][
                "segment"
            ],
            CONFIG[index_name][
                "token"
            ],
            tf["api_interval"],
            tf["chunk_days"],
        )

        candles = prepare_candles(
            rows
        )

        if len(candles) > MAX_CANDLES:

            candles = candles[
                -MAX_CANDLES:
            ]

        print(
            "CANDLES:",
            len(candles)
        )

        if not candles:
            continue

        indicator_states = (
            build_indicator_states(
                candles
            )
        )

        price_action_states = (
            build_price_action_states(
                candles
            )
        )

        prepared[
            timeframe
        ] = (
            candles,
            indicator_states,
            price_action_states,
        )

        results = research_timeframe(
            candles,
            indicator_states,
            price_action_states,
            timeframe
        )

        merge_results(
            index_results,
            results
        )

    if (
        "5M" in prepared
        and "15M" in prepared
    ):

        (
            candles_5m,
            states_5m,
            pa_5m,
        ) = prepared["5M"]

        (
            candles_15m,
            states_15m,
            pa_15m,
        ) = prepared["15M"]

        cross_results = (
            research_cross_timeframe(
                candles_5m,
                states_5m,
                pa_5m,
                candles_15m,
                states_15m
            )
        )

        merge_results(
            index_results,
            cross_results
        )

    print_results(
        f"TOP ENTRY STYLES: "
        f"{index_name}",
        index_results,
        40
    )

    return index_results
def load_api():
    api = MConnect(
        API_KEY
    )

    with open(
        TOKEN_FILE,
        "r"
    ) as file:

        access_token = (
            file.read().strip()
        )

    api.set_access_token(
        access_token
    )

    return api


def main():
    api = load_api()

    combined = defaultdict(
        create_stats
    )

    for index_name in (
        "NIFTY",
        "SENSEX",
    ):

        try:

            results = research_index(
                api,
                index_name
            )

            merge_results(
                combined,
                results
            )

        except Exception as error:

            print(
                "\nERROR",
                index_name,
                type(error).__name__,
                error
            )

            traceback.print_exc()

    print(
        "\n"
        + "=" * 180
    )

    print(
        "NIFTY + SENSEX COMBINED "
        "BUY ABOVE VS BUY AROUND"
    )

    print_results(
        "FINAL BUY ABOVE VS "
        "BUY AROUND RESULTS",
        combined,
        60
    )


if __name__ == "__main__":
    main()
