from historical.market_behavior_research import (
    fetch_large_history, CONFIG, INTERVAL, CHUNK_DAYS
)
from historical.indicator_combination_research import load_api

MAX_CANDLES = 5000

def parse(row):
    try:
        return {
            "o": float(row[1]),
            "h": float(row[2]),
            "l": float(row[3]),
            "c": float(row[4]),
        }
    except:
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

    # Last step should not lose momentum badly
    momentum = (
        len(moves) < 2
        or moves[-1] >= moves[0] * 0.7
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
        len(moves) < 2
        or moves[-1] >= moves[0] * 0.7
    )

    return progressive and lower_highs and momentum

def test(rows, n, forward):
    candles = [parse(r) for r in rows]
    candles = [x for x in candles if x]

    result = {
        "BULL": {
            "signals": 0, "wins": 0,
            "mfe": 0.0, "mae": 0.0
        },
        "BEAR": {
            "signals": 0, "wins": 0,
            "mfe": 0.0, "mae": 0.0
        },
    }

    for i in range(n - 1, len(candles) - forward):
        window = candles[i-n+1:i+1]
        entry = candles[i]["c"]
        future = candles[i+1:i+1+forward]

        side = None

        if advanced_bull(window):
            side = "BULL"
        elif advanced_bear(window):
            side = "BEAR"

        if not side or not future or entry <= 0:
            continue

        high = max(x["h"] for x in future)
        low = min(x["l"] for x in future)

        if side == "BULL":
            mfe = ((high - entry) / entry) * 100
            mae = ((entry - low) / entry) * 100
        else:
            mfe = ((entry - low) / entry) * 100
            mae = ((high - entry) / entry) * 100

        r = result[side]
        r["signals"] += 1
        r["mfe"] += mfe
        r["mae"] += mae

        # Tradeable move: favorable excursion exceeds adverse excursion
        if mfe > mae:
            r["wins"] += 1

    return result

def test(rows, n, forward):
    candles = [parse(r) for r in rows]
    candles = [x for x in candles if x]

    result = {
        "BULL": {
            "signals": 0,
            "wins": 0,
            "mfe": 0.0,
            "mae": 0.0,
        },
        "BEAR": {
            "signals": 0,
            "wins": 0,
            "mfe": 0.0,
            "mae": 0.0,
        },
    }

    for i in range(n - 1, len(candles) - forward):
        window = candles[i-n+1:i+1]
        entry = candles[i]["c"]
        future = candles[i+1:i+1+forward]

        side = None

        if advanced_bull(window):
            side = "BULL"
        elif advanced_bear(window):
            side = "BEAR"

        if not side or not future or entry <= 0:
            continue

        high = max(x["h"] for x in future)
        low = min(x["l"] for x in future)

        if side == "BULL":
            mfe = ((high - entry) / entry) * 100
            mae = ((entry - low) / entry) * 100
        else:
            mfe = ((entry - low) / entry) * 100
            mae = ((high - entry) / entry) * 100

        r = result[side]

        r["signals"] += 1
        r["mfe"] += mfe
        r["mae"] += mae

        if mfe > mae:
            r["wins"] += 1

    return result

def main():
    api = load_api()

    for name in ("NIFTY", "SENSEX"):
        cfg = CONFIG[name]

        print("\n" + "=" * 90)
        print("FETCHING", name)

        rows = fetch_large_history(
            api,
            cfg["segment"],
            cfg["token"],
            INTERVAL,
            CHUNK_DAYS,
            MAX_CANDLES,
        )

        print(name, "CANDLES:", len(rows))

        for n in (3, 4, 5):
            for forward in (1, 3, 5):

                result = test(
                    rows,
                    n,
                    forward,
                )

                for side in ("BULL", "BEAR"):
                    r = result[side]

                    signals = r["signals"]

                    if signals == 0:
                        continue

                    win_rate = (
                        r["wins"] / signals
                    ) * 100

                    avg_mfe = (
                        r["mfe"] / signals
                    )

                    avg_mae = (
                        r["mae"] / signals
                    )

                    print(
                        name,
                        "| ADV CURVE", n,
                        "| NEXT", forward,
                        "|", side,
                        "| SIGNALS", signals,
                        "| WINS", r["wins"],
                        "| RATE", round(win_rate, 2), "%",
                        "| AVG MFE", round(avg_mfe, 4), "%",
                        "| AVG MAE", round(avg_mae, 4), "%",
                    )


if __name__ == "__main__":
    main()
