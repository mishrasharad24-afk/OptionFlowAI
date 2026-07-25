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

FROM_DATE = "2026-07-01"
TO_DATE = "2026-07-10"

SIGNAL_START = "09:15"
SIGNAL_END = "10:00"

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
                        r[5],
                        "%Y-%m-%d"
                    ).date(),
                    "strike": int(float(r[6])),
                    "type": r[9]
                })

            except:
                pass

    return out


def contract(
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


def candle_map(rows, day):

    return {
        x[0][11:16]: x
        for x in rows
        if x[0].startswith(day)
    }


def fetch(
    m,
    segment,
    token
):

    r = m.get_historical_chart(
        segment,
        str(token),
        "5minute",
        FROM_DATE,
        TO_DATE
    )

    return get_candles(r)


def run_index(
    m,
    index
):

    cfg = CONFIG[index]

    print(
        "\n"
        + "=" * 90
    )

    print(
        "BACKTEST:",
        index
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

            if i < 1:
                continue

            spot = float(
                smap[t][4]
            )

            prev_spot = float(
                smap[times[i - 1]][4]
            )

            spot_move = (
                spot - prev_spot
            )

            atm = int(
                round(
                    spot / cfg["gap"]
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

                ce = contract(
                    contracts,
                    expiry,
                    strike,
                    "CE"
                )

                pe = contract(
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

                if (
                    t not in cem
                    or t not in pem
                    or times[i - 1] not in cem
                    or times[i - 1] not in pem
                ):
                    continue

                ct = cem[t]
                cp = cem[times[i - 1]]

                pt = pem[t]
                pp = pem[times[i - 1]]

                ce_mom = float(ct[4]) - float(cp[4])
                pe_mom = float(pt[4]) - float(pp[4])

                if ce_mom > 0:
                    ce_up += 1

                if ce_mom < 0:
                    ce_down += 1

                if pe_mom > 0:
                    pe_up += 1

                if pe_mom < 0:
                    pe_down += 1

                if float(ct[5]) > float(cp[5]):
                    ce_vol += 1

                if float(pt[5]) > float(pp[5]):
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

            if (
                spot_move > 0
                and ce_up >= 4
                and pe_down >= 4
                and ce_vol >= 2
            ):
                signal = "CE"
                selected = current_atm_ce

            elif (
                spot_move < 0
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

            future = [
                x for tm, x in omap.items()
                if tm >= t
            ]

            if not future:
                continue

            max_high = max(
                float(x[2])
                for x in future
            )

            min_low = min(
                float(x[3])
                for x in future
            )

            mfe = (
                max_high - entry
            )

            mae = (
                entry - min_low
            )

            result = {
                "day": day,
                "signal": signal,
                "time": t,
                "spot": spot,
                "atm": atm,
                "entry": entry,
                "mfe": mfe,
                "mae": mae,
                "breadth": valid
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
                f"MFE +{mfe:.2f} | "
                f"MAE -{mae:.2f}"
            )

            signal_found = True
            break

        if not signal_found:

            print(
                day,
                "| NO SIGNAL"
            )

    print(
        "\nSUMMARY",
        index
    )

    print(
        "DAYS    :",
        len(days)
    )

    print(
        "SIGNALS :",
        len(results)
    )

    if results:

        good = sum(
            1 for x in results
            if x["mfe"] > x["mae"]
        )

        print(
            "MFE > MAE:",
            good,
            "/",
            len(results)
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
