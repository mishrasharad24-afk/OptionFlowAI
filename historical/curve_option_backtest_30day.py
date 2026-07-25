import csv
from datetime import datetime, timedelta

from tradingapi_a.mconnect import MConnect
from config.settings import API_KEY

TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"
MASTER_FILE = "/home/ec2-user/OptionFlowAI/instrument_master.csv"

# ===== MULTI-DAY NIFTY TEST =====
INDEX = "NIFTY"
DAYS_BACK = 30
INTERVAL = "5minute"

CONFIG = {
    "spot_seg": "NSE",
    "spot_token": "26000",
    "opt_seg": "NFO",
    "gap": 50,
}

# Avoid treating same continuous curve as many trades
SIGNAL_COOLDOWN_MINUTES = 15

# Cache option history:
# key = (token, date)
OPTION_CACHE = {}


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


def parse(row):
    try:
        return {
            "time": str(row[0]),
            "dt": datetime.fromisoformat(
                str(row[0])
            ),
            "o": float(row[1]),
            "h": float(row[2]),
            "l": float(row[3]),
            "c": float(row[4]),
        }
    except Exception:
        return None


def load_contracts():
    result = []

    with open(
        MASTER_FILE,
        "r",
        errors="ignore",
    ) as f:

        for row in csv.reader(f):

            if len(row) < 12:
                continue

            try:
                if row[3] != INDEX:
                    continue

                if row[9] not in (
                    "CE",
                    "PE",
                ):
                    continue

                result.append({
                    "token": row[0],
                    "symbol": row[2],
                    "expiry": datetime.strptime(
                        row[5],
                        "%Y-%m-%d",
                    ).date(),
                    "strike": int(
                        float(row[6])
                    ),
                    "type": row[9],
                })

            except Exception:
                pass

    return result

def advanced_bull(x):
    moves = [
        x[i]["c"] - x[i-1]["c"]
        for i in range(1, len(x))
    ]

    progressive = all(
        m > 0
        for m in moves
    )

    higher_lows = all(
        x[i]["l"] >= x[i-1]["l"]
        for i in range(1, len(x))
    )

    momentum = (
        moves[-1] >= moves[0] * 0.7
    )

    return (
        progressive
        and higher_lows
        and momentum
    )


def advanced_bear(x):
    moves = [
        x[i-1]["c"] - x[i]["c"]
        for i in range(1, len(x))
    ]

    progressive = all(
        m > 0
        for m in moves
    )

    lower_highs = all(
        x[i]["h"] <= x[i-1]["h"]
        for i in range(1, len(x))
    )

    momentum = (
        moves[-1] >= moves[0] * 0.7
    )

    return (
        progressive
        and lower_highs
        and momentum
    )


def fetch_spot_history(m):
    all_rows = []

    end = datetime.now()
    start_limit = (
        end - timedelta(days=DAYS_BACK)
    )

    cursor = start_limit

    while cursor < end:
        chunk_end = min(
            cursor + timedelta(days=7),
            end,
        )

        try:
            response = m.get_historical_chart(
                CONFIG["spot_seg"],
                CONFIG["spot_token"],
                INTERVAL,
                cursor.strftime("%Y-%m-%d"),
                chunk_end.strftime("%Y-%m-%d"),
            )

            all_rows.extend(
                get_candles(response)
            )

        except Exception as e:
            print(
                "SPOT FETCH ERROR",
                cursor.strftime("%Y-%m-%d"),
                type(e).__name__,
                e,
            )

        cursor = (
            chunk_end
            + timedelta(days=1)
        )

    unique = {
        str(row[0]): row
        for row in all_rows
        if row
    }

    return sorted(
        unique.values(),
        key=lambda x: x[0],
    )


def find_curve_signals(rows):
    candles = [
        parse(row)
        for row in rows
    ]

    candles = [
        x for x in candles
        if x
    ]

    signals = []

    last_signal = {
        "CE": None,
        "PE": None,
    }

    for i in range(
        4,
        len(candles),
    ):
        window = candles[
            i-4:i+1
        ]

        current = candles[i]

        # Never allow a 5-candle curve
        # to cross two trading dates
        dates = {
            x["dt"].date()
            for x in window
        }

        if len(dates) != 1:
            continue

        side = None

        if advanced_bull(window):
            side = "CE"

        elif advanced_bear(window):
            side = "PE"

        if side is None:
            continue

        previous = last_signal[side]

        if previous is not None:
            minutes = (
                current["dt"]
                - previous
            ).total_seconds() / 60

            if (
                minutes
                < SIGNAL_COOLDOWN_MINUTES
            ):
                continue

        spot = current["c"]

        atm = int(
            round(
                spot
                / CONFIG["gap"]
            )
            * CONFIG["gap"]
        )

        signals.append({
            "time": current["time"],
            "dt": current["dt"],
            "date": current["dt"].date(),
            "side": side,
            "spot": spot,
            "atm": atm,
        })

        last_signal[side] = current["dt"]

    return signals

def find_contract(
    contracts,
    signal_date,
    atm,
    side,
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
            and x["type"] == side
        ),
        None,
    )


def get_option_day(
    m,
    contract,
    signal_date,
):
    date_text = signal_date.strftime(
        "%Y-%m-%d"
    )

    cache_key = (
        contract["token"],
        date_text,
    )

    if cache_key in OPTION_CACHE:
        return OPTION_CACHE[
            cache_key
        ]

    to_date = (
        signal_date
        + timedelta(days=1)
    ).strftime("%Y-%m-%d")

    try:
        response = m.get_historical_chart(
            CONFIG["opt_seg"],
            contract["token"],
            INTERVAL,
            date_text,
            to_date,
        )

        rows = get_candles(
            response
        )

    except Exception as e:
        print(
            "OPTION FETCH ERROR",
            contract["symbol"],
            date_text,
            type(e).__name__,
            e,
        )

        rows = []

    data = []

    for row in rows:
        candle = parse(row)

        if (
            candle
            and candle["dt"].date()
            == signal_date
        ):
            data.append(candle)

    data = sorted(
        data,
        key=lambda x: x["dt"],
    )

    OPTION_CACHE[
        cache_key
    ] = data

    return data


def analyze_signal(
    m,
    contracts,
    signal,
):
    contract = find_contract(
        contracts,
        signal["date"],
        signal["atm"],
        signal["side"],
    )

    if not contract:
        return None

    data = get_option_day(
        m,
        contract,
        signal["date"],
    )

    if not data:
        return None

    pos = None

    for i, candle in enumerate(data):

        if (
            candle["dt"]
            == signal["dt"]
        ):
            pos = i
            break

    if pos is None:
        return None

    entry = data[pos]["c"]

    if entry <= 0:
        return None

    result = {
        "symbol": contract["symbol"],
        "entry": entry,
        "side": signal["side"],
    }

    for forward in (
        1,
        3,
        5,
    ):
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

def new_stats():
    return {
        1: {
            "total": 0,
            "wins": 0,
            "mfe": 0.0,
            "mae": 0.0,
        },
        3: {
            "total": 0,
            "wins": 0,
            "mfe": 0.0,
            "mae": 0.0,
        },
        5: {
            "total": 0,
            "wins": 0,
            "mfe": 0.0,
            "mae": 0.0,
        },
    }


def main():
    token = open(
        TOKEN_FILE
    ).read().strip()

    m = MConnect(
        api_key=API_KEY,
        access_Token=token,
    )

    print(
        "=" * 90
    )
    print(
        "NIFTY MULTI-DAY OPTION CURVE BACKTEST"
    )
    print(
        "DAYS BACK:",
        DAYS_BACK
    )
    print(
        "COOLDOWN:",
        SIGNAL_COOLDOWN_MINUTES,
        "MINUTES"
    )

    contracts = load_contracts()

    print(
        "OPTION CONTRACTS:",
        len(contracts)
    )

    spot_rows = fetch_spot_history(
        m
    )

    print(
        "SPOT CANDLES:",
        len(spot_rows)
    )

    signals = find_curve_signals(
        spot_rows
    )

    print(
        "CURVE SIGNALS AFTER COOLDOWN:",
        len(signals)
    )

    stats = {
        "CE": new_stats(),
        "PE": new_stats(),
    }

    valid_signals = 0
    skipped_signals = 0

    for number, signal in enumerate(
        signals,
        1,
    ):
        try:
            result = analyze_signal(
                m,
                contracts,
                signal,
            )

        except Exception as e:
            print(
                "SIGNAL ERROR",
                signal["time"],
                signal["side"],
                type(e).__name__,
                e,
            )

            skipped_signals += 1
            continue

        if not result:
            skipped_signals += 1
            continue

        valid_signals += 1

        print(
            "VALID",
            number,
            "|",
            signal["time"],
            "|",
            signal["side"],
            "| ATM",
            signal["atm"],
            "| ENTRY",
            round(
                result["entry"],
                2
            ),
        )

        for forward in (
            1,
            3,
            5,
        ):
            r = result.get(
                forward
            )

            if not r:
                continue

            s = stats[
                signal["side"]
            ][forward]

            s["total"] += 1
            s["mfe"] += r["mfe"]
            s["mae"] += r["mae"]

            # Same rule as advanced spot test:
            # favorable excursion must beat
            # adverse excursion.
            if r["mfe"] > r["mae"]:
                s["wins"] += 1

    print(
        "\n" + "=" * 90
    )

    print(
        "FINAL RESULT"
    )

    print(
        "VALID SIGNALS:",
        valid_signals
    )

    print(
        "SKIPPED SIGNALS:",
        skipped_signals
    )

    for side in (
        "CE",
        "PE",
    ):
        print(
            "\nSIDE:",
            side
        )

        for forward in (
            1,
            3,
            5,
        ):
            s = stats[
                side
            ][forward]

            total = s["total"]

            if total == 0:
                print(
                    "NEXT",
                    forward,
                    "| NO DATA"
                )
                continue

            win_rate = (
                s["wins"]
                / total
            ) * 100

            avg_mfe = (
                s["mfe"]
                / total
            )

            avg_mae = (
                s["mae"]
                / total
            )

            print(
                "NEXT",
                forward,
                "| SIGNALS",
                total,
                "| WINS",
                s["wins"],
                "| RATE",
                round(
                    win_rate,
                    2
                ),
                "%",
                "| AVG MFE",
                round(
                    avg_mfe,
                    2
                ),
                "%",
                "| AVG MAE",
                round(
                    avg_mae,
                    2
                ),
                "%",
            )


if __name__ == "__main__":
    main()
