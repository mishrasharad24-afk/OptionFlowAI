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
# ADVANCED TRADE STYLE BACKTEST
#
# ENTRY:
#   BUY AROUND = signal candle close
#
# EXIT:
#   Target
#   Stop Loss
#   MTM exit at final hold candle close
#
# METRICS:
#   Win Rate
#   Net R
#   Expectancy
#   Profit Factor
#   Max Drawdown
#   Max Consecutive Losses
#
# TIMEFRAMES:
#   5M
#   15M
#   5M + 15M
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
    1,
    3,
    5,
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


def create_trade_stats():
    return {
        "total": 0,
        "wins": 0,
        "losses": 0,
        "target_hits": 0,
        "sl_hits": 0,
        "mtm_exits": 0,
        "net_r": 0.0,
        "gross_profit_r": 0.0,
        "gross_loss_r": 0.0,
        "trade_returns": [],
    }


def calculate_trade_levels(
    candle,
    signal,
    rr
):
    entry = safe_float(
        candle["close"]
    )

    high = safe_float(
        candle["high"]
    )

    low = safe_float(
        candle["low"]
    )

    if entry <= 0:
        return None

    if signal == "BULLISH":

        stop_loss = low

        risk = (
            entry - stop_loss
        )

        if risk <= 0:
            return None

        target = (
            entry
            + risk * rr
        )

    elif signal == "BEARISH":

        stop_loss = high

        risk = (
            stop_loss - entry
        )

        if risk <= 0:
            return None

        target = (
            entry
            - risk * rr
        )

    else:
        return None

    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "risk": risk,
    }


def simulate_trade(
    candles,
    signal_index,
    signal,
    rr,
    max_hold
):
    levels = calculate_trade_levels(
        candles[signal_index],
        signal,
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

    last_index = (
        end_index - 1
    )

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

        # Conservative assumption:
        # if SL and target touch same candle,
        # count SL first.

        if sl_hit and target_hit:
            return {
                "type": "SL",
                "r": -1.0,
            }

        if sl_hit:
            return {
                "type": "SL",
                "r": -1.0,
            }

        if target_hit:
            return {
                "type": "TARGET",
                "r": rr,
            }

    final_close = safe_float(
        candles[last_index]["close"]
    )

    if signal == "BULLISH":

        mtm_r = (
            final_close - entry
        ) / risk

    else:

        mtm_r = (
            entry - final_close
        ) / risk

    # MTM cannot exceed target or SL
    # because those would already have exited.

    mtm_r = max(
        -1.0,
        min(
            rr,
            mtm_r
        )
    )

    return {
        "type": "MTM",
        "r": mtm_r,
    }


def update_trade_stats(
    stats,
    result
):
    if result is None:
        return

    trade_r = result["r"]
    exit_type = result["type"]

    stats["total"] += 1

    stats[
        "trade_returns"
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

    if exit_type == "TARGET":

        stats[
            "target_hits"
        ] += 1

    elif exit_type == "SL":

        stats[
            "sl_hits"
        ] += 1

    elif exit_type == "MTM":

        stats[
            "mtm_exits"
        ] += 1
def research_trade_timeframe(
    candles,
    indicator_states,
    price_action_states,
    timeframe
):
    results = defaultdict(
        create_trade_stats
    )

    qualified = 0

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

            qualified += 1

            for rr in RR_VALUES:

                for max_hold in (
                    MAX_HOLD_WINDOWS
                ):

                    result = simulate_trade(
                        candles,
                        i,
                        signal,
                        rr,
                        max_hold
                    )

                    key = (
                        timeframe,
                        regime,
                        combination,
                        signal,
                        rr,
                        max_hold,
                    )

                    update_trade_stats(
                        results[key],
                        result
                    )

    print(
        f"\nTRADE BACKTEST {timeframe}"
    )

    print(
        "QUALIFIED SIGNALS:",
        qualified
    )

    return results


def research_trade_cross_timeframe(
    candles_5m,
    states_5m,
    price_action_5m,
    candles_15m,
    states_15m
):
    results = defaultdict(
        create_trade_stats
    )

    state_map_15m = (
        build_15m_state_map(
            candles_15m,
            states_15m
        )
    )

    matched = 0
    qualified = 0

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

        matched += 1

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

            qualified += 1

            for rr in RR_VALUES:

                for max_hold in (
                    MAX_HOLD_WINDOWS
                ):

                    result = simulate_trade(
                        candles_5m,
                        i,
                        signal,
                        rr,
                        max_hold
                    )

                    key = (
                        "5M+15M",
                        regime,
                        combination,
                        signal,
                        rr,
                        max_hold,
                    )

                    update_trade_stats(
                        results[key],
                        result
                    )

    print(
        "\n5M+15M MATCHED:",
        matched
    )

    print(
        "5M+15M QUALIFIED:",
        qualified
    )

    return results


def merge_trade_results(
    target,
    source
):
    for key, stats in source.items():

        target_stats = target[key]

        for field in (
            "total",
            "wins",
            "losses",
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
            "trade_returns"
        ].extend(
            stats[
                "trade_returns"
            ]
        )


def calculate_max_drawdown(
    returns
):
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for trade_r in returns:

        equity += trade_r

        if equity > peak:
            peak = equity

        drawdown = (
            peak - equity
        )

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return max_drawdown


def calculate_max_consecutive_losses(
    returns
):
    current_losses = 0
    max_losses = 0

    for trade_r in returns:

        if trade_r < 0:

            current_losses += 1

            max_losses = max(
                max_losses,
                current_losses
            )

        else:

            current_losses = 0

    return max_losses


def calculate_trade_metrics(
    stats
):
    total = stats["total"]

    if total <= 0:
        return None

    wins = stats["wins"]
    losses = stats["losses"]

    win_rate = (
        wins / total
    ) * 100.0

    net_r = stats["net_r"]

    expectancy = (
        net_r / total
    )

    gross_profit = (
        stats["gross_profit_r"]
    )

    gross_loss = (
        stats["gross_loss_r"]
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

    max_drawdown = (
        calculate_max_drawdown(
            stats["trade_returns"]
        )
    )

    max_consecutive_losses = (
        calculate_max_consecutive_losses(
            stats["trade_returns"]
        )
    )

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "net_r": net_r,
        "expectancy": expectancy,
        "profit_factor":
            profit_factor,
        "max_drawdown":
            max_drawdown,
        "max_consecutive_losses":
            max_consecutive_losses,
        "target_hits":
            stats["target_hits"],
        "sl_hits":
            stats["sl_hits"],
        "mtm_exits":
            stats["mtm_exits"],
    }
def build_ranked_trade_results(
    results
):
    ranked = []

    for key, stats in results.items():

        metrics = (
            calculate_trade_metrics(
                stats
            )
        )

        if metrics is None:
            continue

        if (
            metrics["total"]
            < MIN_SAMPLE_SIZE
        ):
            continue

        (
            timeframe,
            regime,
            combination,
            signal,
            rr,
            max_hold,
        ) = key

        ranked.append(
            (
                metrics["expectancy"],
                metrics["profit_factor"],
                metrics["win_rate"],
                metrics["total"],
                timeframe,
                regime,
                combination,
                signal,
                rr,
                max_hold,
                metrics["net_r"],
                metrics["max_drawdown"],
                metrics[
                    "max_consecutive_losses"
                ],
                metrics["target_hits"],
                metrics["sl_hits"],
                metrics["mtm_exits"],
            )
        )

    ranked.sort(
        key=lambda row: (
            row[0],
            row[1],
            row[3],
        ),
        reverse=True
    )

    return ranked


def print_trade_results(
    title,
    results,
    limit=30
):
    print(
        "\n"
        + "=" * 160
    )

    print(title)

    ranked = (
        build_ranked_trade_results(
            results
        )
    )

    if not ranked:

        print(
            "NO QUALIFIED RESULTS"
        )

        return []

    for row in ranked[:limit]:

        (
            expectancy,
            profit_factor,
            win_rate,
            total,
            timeframe,
            regime,
            combination,
            signal,
            rr,
            max_hold,
            net_r,
            max_drawdown,
            max_losses,
            target_hits,
            sl_hits,
            mtm_exits,
        ) = row

        print(
            f"{timeframe:<7} | "
            f"{regime:<12} | "
            f"{signal:<7} | "
            f"{combination:<55} | "
            f"RR 1:{rr:<3} | "
            f"HOLD {max_hold:<2} | "
            f"N {total:<4} | "
            f"WIN {win_rate:6.2f}% | "
            f"EXP {expectancy:+.3f}R | "
            f"PF {profit_factor:5.2f} | "
            f"NET {net_r:+.2f}R | "
            f"DD {max_drawdown:.2f}R | "
            f"MAXL {max_losses:<2} | "
            f"TGT {target_hits:<3} | "
            f"SL {sl_hits:<3} | "
            f"MTM {mtm_exits:<3}"
        )

    return ranked


def print_best_by_regime(
    title,
    results,
    limit_per_regime=10
):
    print(
        "\n"
        + "=" * 160
    )

    print(title)

    ranked = (
        build_ranked_trade_results(
            results
        )
    )

    grouped = defaultdict(
        list
    )

    for row in ranked:

        regime = row[5]

        grouped[
            regime
        ].append(
            row
        )

    for regime in sorted(
        grouped.keys()
    ):

        print(
            "\n"
            + "-" * 160
        )

        print(
            "REGIME:",
            regime
        )

        for row in grouped[
            regime
        ][
            :limit_per_regime
        ]:

            (
                expectancy,
                profit_factor,
                win_rate,
                total,
                timeframe,
                regime_name,
                combination,
                signal,
                rr,
                max_hold,
                net_r,
                max_drawdown,
                max_losses,
                target_hits,
                sl_hits,
                mtm_exits,
            ) = row

            print(
                f"{timeframe:<7} | "
                f"{signal:<7} | "
                f"{combination:<55} | "
                f"RR 1:{rr:<3} | "
                f"HOLD {max_hold:<2} | "
                f"N {total:<4} | "
                f"WIN {win_rate:6.2f}% | "
                f"EXP {expectancy:+.3f}R | "
                f"PF {profit_factor:5.2f} | "
                f"NET {net_r:+.2f}R | "
                f"DD {max_drawdown:.2f}R | "
                f"MAXL {max_losses:<2} | "
                f"TGT {target_hits:<3} | "
                f"SL {sl_hits:<3} | "
                f"MTM {mtm_exits:<3}"
            )


def research_index(
    api,
    index_name
):
    print(
        "\n"
        + "#" * 160
    )

    print(
        "ADVANCED TRADE BACKTEST:",
        index_name
    )

    index_results = defaultdict(
        create_trade_stats
    )

    prepared_data = {}

    for timeframe in (
        RESEARCH_TIMEFRAMES
    ):

        tf_config = (
            TIMEFRAMES[
                timeframe
            ]
        )

        print(
            f"\nFETCHING "
            f"{index_name} "
            f"{timeframe}"
        )

        rows = fetch_max_950(
            api,
            CONFIG[index_name][
                "segment"
            ],
            CONFIG[index_name][
                "token"
            ],
            tf_config[
                "api_interval"
            ],
            tf_config[
                "chunk_days"
            ],
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

        prepared_data[
            timeframe
        ] = (
            candles,
            indicator_states,
            price_action_states,
        )

        results = (
            research_trade_timeframe(
                candles,
                indicator_states,
                price_action_states,
                timeframe
            )
        )

        merge_trade_results(
            index_results,
            results
        )

    if (
        "5M" in prepared_data
        and "15M" in prepared_data
    ):

        (
            candles_5m,
            states_5m,
            price_action_5m,
        ) = prepared_data["5M"]

        (
            candles_15m,
            states_15m,
            price_action_15m,
        ) = prepared_data["15M"]

        cross_results = (
            research_trade_cross_timeframe(
                candles_5m,
                states_5m,
                price_action_5m,
                candles_15m,
                states_15m
            )
        )

        merge_trade_results(
            index_results,
            cross_results
        )

    print_trade_results(
        f"TOP 30 ADVANCED TRADES: "
        f"{index_name}",
        index_results,
        30
    )

    print_best_by_regime(
        f"BEST ADVANCED TRADES "
        f"BY REGIME: {index_name}",
        index_results,
        10
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

    combined_results = defaultdict(
        create_trade_stats
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

            merge_trade_results(
                combined_results,
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
        + "=" * 160
    )

    print(
        "NIFTY + SENSEX COMBINED "
        "ADVANCED TRADE BACKTEST"
    )

    print_trade_results(
        "FINAL TOP 30 ADVANCED "
        "TRADE SETUPS",
        combined_results,
        30
    )

    print_best_by_regime(
        "FINAL BEST ADVANCED "
        "TRADE SETUPS BY REGIME",
        combined_results,
        10
    )


if __name__ == "__main__":
    main()
