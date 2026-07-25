import sys, os, csv
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY

TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"
MASTER_FILE = "/home/ec2-user/OptionFlowAI/instrument_master.csv"

FROM_DATE = "2026-07-09"
TO_DATE = "2026-07-10"

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


def candles(resp):
    try:
        return resp.json().get("data", {}).get("candles") or []
    except Exception:
        return []


def only_test_day(rows):
    return sorted(
        [x for x in rows if str(x[0]).startswith(FROM_DATE)],
        key=lambda x: x[0]
    )


def load_contracts(index):

    result = []

    with open(MASTER_FILE, "r", errors="ignore") as f:

        for row in csv.reader(f):

            if len(row) < 12:
                continue

            try:
                if row[3] != index:
                    continue

                if row[9] not in ("CE", "PE"):
                    continue

                expiry = datetime.strptime(
                    row[5],
                    "%Y-%m-%d"
                ).date()

                result.append({
                    "token": row[0],
                    "symbol": row[2],
                    "expiry": expiry,
                    "strike": int(float(row[6])),
                    "type": row[9],
                    "exchange": row[11]
                })

            except Exception:
                pass

    return result


def run(m, index):

    cfg = CONFIG[index]

    print("\n" + "=" * 70)
    print("INDEX :", index)
    print("DATE  :", FROM_DATE)

    # SPOT HISTORY
    r = m.get_historical_chart(
        cfg["spot_seg"],
        cfg["spot_token"],
        "5minute",
        FROM_DATE,
        TO_DATE
    )

    spot = only_test_day(candles(r))

    if not spot:
        print("NO SPOT DATA")
        return

    opening = spot[0]
    spot_price = float(opening[4])

    atm = int(
        round(spot_price / cfg["gap"])
        * cfg["gap"]
    )

    print("OPEN TIME :", opening[0])
    print("SPOT      :", spot_price)
    print("ATM       :", atm)

    # OPTION MASTER
    contracts = load_contracts(index)

    test_date = datetime.strptime(
        FROM_DATE,
        "%Y-%m-%d"
    ).date()

    expiries = sorted({
        x["expiry"]
        for x in contracts
        if x["expiry"] >= test_date
    })

    if not expiries:
        print("NO EXPIRY")
        return

    expiry = expiries[0]

    print("EXPIRY    :", expiry)

    ce = next(
        (
            x for x in contracts
            if x["expiry"] == expiry
            and x["strike"] == atm
            and x["type"] == "CE"
        ),
        None
    )

    pe = next(
        (
            x for x in contracts
            if x["expiry"] == expiry
            and x["strike"] == atm
            and x["type"] == "PE"
        ),
        None
    )

    if not ce or not pe:
        print("ATM CE/PE NOT FOUND")
        return

    print("CE :", ce["symbol"], ce["token"])
    print("PE :", pe["symbol"], pe["token"])

    # CE HISTORY
    r = m.get_historical_chart(
        cfg["opt_seg"],
        ce["token"],
        "5minute",
        FROM_DATE,
        TO_DATE
    )

    ce_data = only_test_day(candles(r))

    # PE HISTORY
    r = m.get_historical_chart(
        cfg["opt_seg"],
        pe["token"],
        "5minute",
        FROM_DATE,
        TO_DATE
    )

    pe_data = only_test_day(candles(r))

    print("CE CANDLES :", len(ce_data))
    print("PE CANDLES :", len(pe_data))

    if ce_data:
        print("CE FIRST :", ce_data[0])
        print("CE LAST  :", ce_data[-1])

    if pe_data:
        print("PE FIRST :", pe_data[0])
        print("PE LAST  :", pe_data[-1])


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
            run(m, index)

        except Exception as e:
            print(
                "ERROR",
                index,
                type(e).__name__,
                e
            )


if __name__ == "__main__":
    main()
