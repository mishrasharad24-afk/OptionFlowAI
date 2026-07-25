import sys, os, csv
from datetime import datetime

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY

TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"
MASTER_FILE = "/home/ec2-user/OptionFlowAI/instrument_master.csv"

FROM_DATE = "2026-06-15"
TO_DATE = "2026-07-10"

SIGNAL_START = "09:15"
SIGNAL_END = "10:00"

TARGET_PCT = 20
SL_PCT = 15

CONFIG = {
    "NIFTY": {
        "spot_seg": "NSE",
        "spot_token": "26000",
        "opt_seg": "NFO",
        "gap": 50
    },
    "SENSEX": {
        "spot_seg": "BSE",
        "spot_token": "51",
        "opt_seg": "BFO",
        "gap": 100
    }
}


def get_candles(resp):
    try:
        return resp.json().get(
            "data", {}
        ).get("candles") or []
    except:
        return []


def fetch(m, segment, token):
    from datetime import datetime, timedelta

    start = datetime.strptime(FROM_DATE, "%Y-%m-%d")
    end = datetime.strptime(TO_DATE, "%Y-%m-%d")

    all_rows = []

    while start < end:
        chunk_end = min(
            start + timedelta(days=7),
            end
        )

        r = m.get_historical_chart(
            segment,
            str(token),
            "5minute",
            start.strftime("%Y-%m-%d"),
            chunk_end.strftime("%Y-%m-%d")
        )

        all_rows.extend(
            get_candles(r)
        )

        start = chunk_end

    unique = {
        row[0]: row
        for row in all_rows
    }

    return sorted(
        unique.values(),
        key=lambda x: x[0]
    )


def candle_map(rows, day):
    return {
        x[0][11:16]: x
        for x in rows
        if x[0].startswith(day)
    }


def load_contracts(index):
    out = []

    with open(
        MASTER_FILE,
        "r",
        errors="ignore"
    ) as f:

        for r in csv.reader(f):
            if len(r) < 12:
                continue

            try:
                if r[3] != index:
                    continue

                if r[9] not in ("CE", "PE"):
                    continue

                out.append({
                    "token": r[0],
                    "symbol": r[2],
                    "expiry": datetime.strptime(
                        r[5], "%Y-%m-%d"
                    ).date(),
                    "strike": int(float(r[6])),
                    "type": r[9]
                })
            except:
                pass

    return out


def find_contract(
    contracts,
    expiry,
    strike,
    typ
):
    return next(
        (
            x for x in contracts
            if x["expiry"] == expiry
            and x["strike"] == strike
            and x["type"] == typ
        ),
        None
    )


def evaluate_trade(
    omap,
    entry_time,
    entry
):
    target = entry * (
        1 + TARGET_PCT / 100
    )

    stop = entry * (
        1 - SL_PCT / 100
    )

    future_times = sorted(
        t for t in omap
        if t > entry_time
    )

    result = "OPEN"
    exit_time = "-"

    mfe_15 = 0
    mae_15 = 0
    mfe_30 = 0
    mae_30 = 0
    mfe_60 = 0
    mae_60 = 0

    entry_dt = datetime.strptime(
        entry_time,
        "%H:%M"
    )

    for t in future_times:

        c = omap[t]

        high = float(c[2])
        low = float(c[3])

        now_dt = datetime.strptime(
            t,
            "%H:%M"
        )

        mins = int(
            (
                now_dt - entry_dt
            ).total_seconds() / 60
        )

        gain = high - entry
        loss = entry - low

        if mins <= 15:
            mfe_15 = max(
                mfe_15,
                gain
            )
            mae_15 = max(
                mae_15,
                loss
            )

        if mins <= 30:
            mfe_30 = max(
                mfe_30,
                gain
            )
            mae_30 = max(
                mae_30,
                loss
            )

        if mins <= 60:
            mfe_60 = max(
                mfe_60,
                gain
            )
            mae_60 = max(
                mae_60,
                loss
            )

        if result == "OPEN":

            target_hit = (
                high >= target
            )

            sl_hit = (
                low <= stop
            )

            if target_hit and sl_hit:
                result = "AMBIGUOUS"
                exit_time = t

            elif target_hit:
                result = "WIN"
                exit_time = t

            elif sl_hit:
                result = "LOSS"
                exit_time = t

    return {
        "result": result,
        "exit_time": exit_time,
        "mfe15": mfe_15,
        "mae15": mae_15,
        "mfe30": mfe_30,
        "mae30": mae_30,
        "mfe60": mfe_60,
        "mae60": mae_60
    }
def run_index(m, index):

    cfg = CONFIG[index]

    print("\n" + "=" * 100)
    print("IMPROVED OPENING SNIPER BACKTEST:", index)
    print(
        "TARGET:",
        TARGET_PCT,
        "% | SL:",
        SL_PCT,
        "%"
    )

    spot_all = fetch(
        m,
        cfg["spot_seg"],
        cfg["spot_token"]
    )

    days = sorted({
        x[0][:10]
        for x in spot_all
    })

    contracts = load_contracts(
        index
    )

    cache = {}

    results = []

    for day in days:

        day_date = datetime.strptime(
            day,
            "%Y-%m-%d"
        ).date()

        expiries = sorted({
            x["expiry"]
            for x in contracts
            if x["expiry"] >= day_date
        })

        if not expiries:
            print(day, "| NO EXPIRY")
            continue

        expiry = expiries[0]

        smap = candle_map(
            spot_all,
            day
        )

        times = sorted(
            t for t in smap
            if SIGNAL_START <= t <= SIGNAL_END
        )

        signal_found = False

        for i, t in enumerate(times):

            # Need 2 previous spot candles
            if i < 2:
                continue

            spot_now = float(
                smap[t][4]
            )

            spot_prev1 = float(
                smap[times[i - 1]][4]
            )

            spot_prev2 = float(
                smap[times[i - 2]][4]
            )

            bullish_spot = (
                spot_now > spot_prev1
                and spot_prev1 > spot_prev2
            )

            bearish_spot = (
                spot_now < spot_prev1
                and spot_prev1 < spot_prev2
            )

            if not bullish_spot and not bearish_spot:
                continue

            atm = int(
                round(
                    spot_now / cfg["gap"]
                ) * cfg["gap"]
            )

            strikes = [
                atm + n * cfg["gap"]
                for n in range(-2, 3)
            ]

            ce_up = 0
            pe_down = 0

            pe_up = 0
            ce_down = 0

            ce_vol = 0
            pe_vol = 0

            valid = 0

            current_atm_ce = None
            current_atm_pe = None

            for strike in strikes:

                ce = find_contract(
                    contracts,
                    expiry,
                    strike,
                    "CE"
                )

                pe = find_contract(
                    contracts,
                    expiry,
                    strike,
                    "PE"
                )

                if not ce or not pe:
                    continue

                for opt in (ce, pe):

                    token = opt["token"]

                    if token not in cache:

                        try:
                            cache[token] = fetch(
                                m,
                                cfg["opt_seg"],
                                token
                            )

                        except:
                            cache[token] = []

                cem = candle_map(
                    cache[ce["token"]],
                    day
                )

                pem = candle_map(
                    cache[pe["token"]],
                    day
                )

                prev_time = times[
                    i - 1
                ]

                if (
                    t not in cem
                    or prev_time not in cem
                    or t not in pem
                    or prev_time not in pem
                ):
                    continue

                ce_now = cem[t]
                ce_prev = cem[
                    prev_time
                ]

                pe_now = pem[t]
                pe_prev = pem[
                    prev_time
                ]

                ce_mom = (
                    float(ce_now[4])
                    - float(ce_prev[4])
                )

                pe_mom = (
                    float(pe_now[4])
                    - float(pe_prev[4])
                )

                if ce_mom > 0:
                    ce_up += 1

                elif ce_mom < 0:
                    ce_down += 1

                if pe_mom > 0:
                    pe_up += 1

                elif pe_mom < 0:
                    pe_down += 1

                if (
                    float(ce_now[5])
                    > float(ce_prev[5])
                ):
                    ce_vol += 1

                if (
                    float(pe_now[5])
                    > float(pe_prev[5])
                ):
                    pe_vol += 1

                valid += 1

                if strike == atm:

                    current_atm_ce = (
                        ce,
                        cem
                    )

                    current_atm_pe = (
                        pe,
                        pem
                    )

            signal = None
            selected = None

            # Strong CE confirmation
            if (
                bullish_spot
                and valid >= 4
                and ce_up >= 4
                and pe_down >= 4
                and ce_vol >= 2
            ):

                signal = "CE"
                selected = current_atm_ce

            # Strong PE confirmation
            elif (
                bearish_spot
                and valid >= 4
                and pe_up >= 4
                and ce_down >= 4
                and pe_vol >= 2
            ):

                signal = "PE"
                selected = current_atm_pe

            if not signal or not selected:
                continue

            opt, omap = selected

            if t not in omap:
                continue

            entry = float(
                omap[t][4]
            )

            trade = evaluate_trade(
                omap,
                t,
                entry
            )

            result = {
                "day": day,
                "time": t,
                "signal": signal,
                "atm": atm,
                "entry": entry,
                "result": trade["result"]
            }

            results.append(
                result
            )

            print(
                f"{day} | "
                f"{t} | "
                f"{signal} | "
                f"ATM {atm} | "
                f"ENTRY {entry:.2f} | "
                f"{trade['result']} | "
                f"EXIT {trade['exit_time']}"
            )

            print(
                f"   15M "
                f"MFE +{trade['mfe15']:.2f} "
                f"MAE -{trade['mae15']:.2f} | "
                f"30M "
                f"MFE +{trade['mfe30']:.2f} "
                f"MAE -{trade['mae30']:.2f} | "
                f"60M "
                f"MFE +{trade['mfe60']:.2f} "
                f"MAE -{trade['mae60']:.2f}"
            )

            signal_found = True

            # Only first confirmed signal per day
            break

        if not signal_found:
            print(
                day,
                "| NO SIGNAL"
            )

    wins = sum(
        1 for x in results
        if x["result"] == "WIN"
    )

    losses = sum(
        1 for x in results
        if x["result"] == "LOSS"
    )

    ambiguous = sum(
        1 for x in results
        if x["result"] == "AMBIGUOUS"
    )

    open_trades = sum(
        1 for x in results
        if x["result"] == "OPEN"
    )

    decided = wins + losses

    print("\n" + "-" * 60)

    print(
        "SUMMARY:",
        index
    )

    print(
        "DAYS      :",
        len(days)
    )

    print(
        "SIGNALS   :",
        len(results)
    )

    print(
        "WINS      :",
        wins
    )

    print(
        "LOSSES    :",
        losses
    )

    print(
        "AMBIGUOUS :",
        ambiguous
    )

    print(
        "OPEN      :",
        open_trades
    )

    if decided > 0:

        win_rate = (
            wins / decided
        ) * 100

        print(
            "WIN RATE  :",
            f"{win_rate:.2f}%"
        )

    else:

        print(
            "WIN RATE  : N/A"
        )


def main():

    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token
    )

    for index in (
        "NIFTY",
        "SENSEX"
    ):

        try:

            run_index(
                m,
                index
            )

        except Exception as e:

            print(
                "ERROR",
                index,
                type(e).__name__,
                e
            )


if __name__ == "__main__":
    main()
