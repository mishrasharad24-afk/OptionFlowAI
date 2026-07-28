from tradingapi_a.mconnect import MConnect
import json
import csv

INSTRUMENT_FILE = "/home/ec2-user/OptionFlowAI/instrument_master.csv"

_SYMBOL_CACHE = None
API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="
TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"

KNOWN_EXPIRIES = [
    "1470321000",
]


def _api():
    with open(TOKEN_FILE) as f:
        access_token = f.read().strip()

    return MConnect(
        api_key=API_KEY,
        access_Token=access_token,
    )


def _safe_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except:
        return 0


def _parse_row(row):
    parts = row.split(",")

    if len(parts) < 4:
        return None

    token = parts[0].strip()
    strike = _safe_int(parts[1]) // 100
    buy = _safe_int(parts[2])
    sell = _safe_int(parts[3])

    return {
        "token": token,
        "strike": strike,
        "buy": buy,
        "sell": sell,
    }


def _load_chain(exchange="2", token="26000"):
    api = _api()

    for expiry in KNOWN_EXPIRIES:
        try:
            r = api.get_option_chain_data(
                exchange,
                expiry,
                token,
            )

            j = r.json()

            if (
                j.get("status") == "success"
                and j.get("data")
            ):
                return j

        except Exception:
            continue

    return None


def get_option_chain(exchange="2", token="26000"):
    return _load_chain(exchange, token)


def get_spot(index="NIFTY"):
    api = _api()

    if index.upper() == "SENSEX":
        symbol = "BSE:SENSEX"
    else:
        symbol = "NSE:NIFTY 50"

    r = api.get_ltp([symbol])

    if hasattr(r, "json"):
        r = r.json()

    return float(r["data"][symbol]["last_price"])
def get_step(exchange="2", token="26000"):
    chain = _load_chain(exchange, token)

    if not chain:
        return 50

    calls = chain.get("data", {}).get("call", [])

    strikes = []

    for row in calls:
        parsed = _parse_row(row)

        if parsed:
            strikes.append(parsed["strike"])

    strikes = sorted(set(strikes))

    if len(strikes) >= 2:
        step = strikes[1] - strikes[0]

        if step > 0:
            return step

    return 50


def get_atm(index="NIFTY"):
    spot = get_spot(index)

    if spot is None:
        return None

    step = get_step()

    return round(spot / step) * step


def get_atm_option_chain(
    exchange="2",
    token="26000",
    depth=2,
):
    chain = _load_chain(exchange, token)

    if not chain:
        return None

    spot = get_spot("NIFTY")
    step = get_step(exchange, token)
    atm = round(spot / step) * step

    calls = []
    puts = []

    for row in chain["data"].get("call", []):
        item = _parse_row(row)

        if not item:
            continue

        if abs(item["strike"] - atm) <= depth * step:
            calls.append(item)

    for row in chain["data"].get("put", []):
        item = _parse_row(row)

        if not item:
            continue

        if abs(item["strike"] - atm) <= depth * step:
            puts.append(item)

    calls = sorted(calls, key=lambda x: x["strike"])
    puts = sorted(puts, key=lambda x: x["strike"])
    return {
        "spot": spot,
        "atm": atm,
        "step": step,
        "calls": calls,
        "puts": puts,
    }

def _load_symbol_cache():
    global _SYMBOL_CACHE

    if _SYMBOL_CACHE is not None:
        return _SYMBOL_CACHE

    cache = {}

    with open(INSTRUMENT_FILE, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            token = row["instrument_token"].strip()

            cache[token] = {
                "exchange": row["exchange"].strip(),
                "symbol": row["tradingsymbol"].strip(),
                "strike": row["strike"].strip(),
                "type": row["instrument_type"].strip(),
                "expiry": row["expiry"].strip(),
            }

    _SYMBOL_CACHE = cache
    return cache


def token_to_symbol(token):
    cache = _load_symbol_cache()
    return cache.get(str(token))


def get_option_ltp(token):
    info = token_to_symbol(token)

    if not info:
        return None

    api = _api()

    key = f'{info["exchange"]}:{info["symbol"]}'

    r = api.get_ltp([key])

    if hasattr(r, "json"):
        r = r.json()

    if r.get("status") != "success":
        return None

    data = r["data"][key]

    return {
        "token": token,
        "symbol": info["symbol"],
        "exchange": info["exchange"],
        "ltp": float(data["last_price"]),
    }


if __name__ == "__main__":
    data = get_atm_option_chain()

    print(
        json.dumps(
            data,
            indent=2,
        )
    )

