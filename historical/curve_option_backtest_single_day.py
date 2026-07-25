import csv
from datetime import datetime

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY

TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"
MASTER_FILE = "/home/ec2-user/OptionFlowAI/instrument_master.csv"

# First validate on one trading day
TEST_DATE = "2026-07-09"
TO_DATE = "2026-07-10"

CONFIG = {
    "NIFTY": {
        "spot_seg": "NSE",
        "spot_token": "26000",
        "opt_seg": "NFO",
        "gap": 50,
    },
    "SENSEX": {
        "spot_seg": "BSE",
        "spot_token": "51",
        "opt_seg": "BFO",
        "gap": 100,
    },
}


def get_candles(response):
    try:
        return (
            response.json()
            .get("data", {})
            .get("candles")
            or []
        )
    except Exception:
        return []


def test_day_only(rows):
    return sorted(
        [
            x for x in rows
            if str(x[0]).startswith(TEST_DATE)
        ],
        key=lambda x: x[0],
    )


def load_contracts(index):
    result = []

    with open(
        MASTER_FILE,
        "r",
        errors="ignore"
    ) as f:

        for row in csv.reader(f):

            if len(row) < 12:
                continue

            try:
                if row[3] != index:
                    continue

                if row[9] not in ("CE", "PE"):
                    continue

                result.append({
                    "token": row[0],
                    "symbol": row[2],
                    "expiry": datetime.strptime(
                        row[5],
                        "%Y-%m-%d"
                    ).date(),
                    "strike": int(float(row[6])),
                    "type": row[9],
                    "exchange": row[11],
                })

            except Exception:
                pass

    return result

def parse(row):
    try:
        return {
            "time": str(row[0]),
            "o": float(row[1]),
            "h": float(row[2]),
            "l": float(row[3]),
            "c": float(row[4]),
        }
    except Exception:
        return None


def advanced_bull(x):
    moves = [
        x[i]["c"] - x[i-1]["c"]
        for i in range(1, len(x))
    ]

    progressive = all(m > 0 for m in moves)

    higher_lows = all(
        x[i]["l"] >= x[i-1]["l"]
        for i in range(1, len(x))
    )

    momentum = (
        moves[-1] >= moves[0] * 0.7
    )

    return progressive and higher_lows and momentum


def advanced_bear(x):
    moves = [
        x[i-1]["c"] - x[i]["c"]
        for i in range(1, len(x))
    ]

    progressive = all(m > 0 for m in moves)

    lower_highs = all(
        x[i]["h"] <= x[i-1]["h"]
        for i in range(1, len(x))
    )

    momentum = (
        moves[-1] >= moves[0] * 0.7
    )

    return progressive and lower_highs and momentum


def find_contract(
    contracts,
    signal_date,
    atm,
    option_type,
):
    expiries = sorted({
        x["expiry"]
        for x in contracts
        if x["expiry"] >= signal_date
    })

    if not expiries:
        return None

    expiry = expiries[0]

    return next(
        (
            x for x in contracts
            if x["expiry"] == expiry
            and x["strike"] == atm
            and x["type"] == option_type
        ),
        None,
    )


def find_curve_signals(spot_rows, gap):
    candles = [
        parse(x)
        for x in spot_rows
    ]

    candles = [
        x for x in candles
        if x
    ]

    signals = []

    # Fixed 5-candle Advanced Curve
    for i in range(4, len(candles)):
        window = candles[i-4:i+1]
        spot = candles[i]["c"]

        atm = int(
            round(spot / gap)
            * gap
        )

        if advanced_bull(window):
            signals.append({
                "time": candles[i]["time"],
                "side": "CE",
                "spot": spot,
                "atm": atm,
            })

        elif advanced_bear(window):
            signals.append({
                "time": candles[i]["time"],
                "side": "PE",
                "spot": spot,
                "atm": atm,
            })

    return signals

def analyze_option(
    m,
    cfg,
    contract,
    signal_time,
):
    response = m.get_historical_chart(
        cfg["opt_seg"],
        contract["token"],
        "5minute",
        TEST_DATE,
        TO_DATE,
    )

    rows = test_day_only(
        get_candles(response)
    )

    data = [
        parse(x)
        for x in rows
    ]

    data = [
        x for x in data
        if x
    ]

    if not data:
        return None

    # Find exact signal-time option candle
    pos = None

    for i, candle in enumerate(data):
        if candle["time"] == signal_time:
            pos = i
            break

    if pos is None:
        return None

    entry = data[pos]["c"]

    if entry <= 0:
        return None

    result = {
        "entry": entry,
    }

    for forward in (1, 3, 5):

        future = data[
            pos + 1:
            pos + 1 + forward
        ]

        if not future:
            continue

        high = max(
            x["h"]
            for x in future
        )

        low = min(
            x["l"]
            for x in future
        )

        mfe = (
            (high - entry)
            / entry
        ) * 100

        mae = (
            (entry - low)
            / entry
        ) * 100

        result[forward] = {
            "mfe": mfe,
            "mae": mae,
        }

    return result


def run_index(m, index):
    cfg = CONFIG[index]

    print("\n" + "=" * 90)
    print("INDEX:", index)
    print("DATE :", TEST_DATE)

    response = m.get_historical_chart(
        cfg["spot_seg"],
        cfg["spot_token"],
        "5minute",
        TEST_DATE,
        TO_DATE,
    )

    spot_rows = test_day_only(
        get_candles(response)
    )

    print(
        "SPOT CANDLES:",
        len(spot_rows)
    )

    if not spot_rows:
        return

    contracts = load_contracts(index)

    signals = find_curve_signals(
        spot_rows,
        cfg["gap"],
    )

    print(
        "CURVE SIGNALS:",
        len(signals)
    )

    signal_date = datetime.strptime(
        TEST_DATE,
        "%Y-%m-%d"
    ).date()

    for signal in signals:

        contract = find_contract(
            contracts,
            signal_date,
            signal["atm"],
            signal["side"],
        )

        if not contract:
            print(
                "CONTRACT NOT FOUND:",
                signal
            )
            continue

        result = analyze_option(
            m,
            cfg,
            contract,
            signal["time"],
        )

        if not result:
            print(
                "OPTION DATA NOT FOUND:",
                signal["time"],
                contract["symbol"],
            )
            continue

        print(
            "\nSIGNAL",
            signal["time"],
            "|", signal["side"],
            "| SPOT", signal["spot"],
            "| ATM", signal["atm"],
            "| OPTION", contract["symbol"],
            "| ENTRY", result["entry"],
        )

        for forward in (1, 3, 5):

            r = result.get(forward)

            if not r:
                continue

            print(
                " NEXT", forward,
                "| MFE",
                round(r["mfe"], 2), "%",
                "| MAE",
                round(r["mae"], 2), "%",
            )


def main():
    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    for index in (
        "NIFTY",
        "SENSEX",
    ):
        try:
            run_index(
                m,
                index,
            )

        except Exception as e:
            print(
                "ERROR",
                index,
                type(e).__name__,
                e,
            )


if __name__ == "__main__":
    main()
