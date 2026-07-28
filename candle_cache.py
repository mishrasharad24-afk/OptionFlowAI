import json
import os
from threading import Lock

_CACHE_DIR = "cache"
_LOCK = Lock()


def _cache_file(index_name):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"{index_name.lower()}_intraday.json")


def load_intraday_cache(index_name):
    path = _cache_file(index_name)
    if not os.path.exists(path):
        return {"5M": [], "15M": []}

    try:
        with open(path, "r") as f:
            data = json.load(f)
        return {
            "5M": data.get("5M", []),
            "15M": data.get("15M", []),
        }
    except Exception:
        return {"5M": [], "15M": []}


def save_intraday_cache(index_name, tf, candles):
    with _LOCK:
        data = load_intraday_cache(index_name)
        data[tf] = candles

        with open(_cache_file(index_name), "w") as f:
            json.dump(data, f)


def merge_intraday_history(history_rows, intraday_rows):
    if not intraday_rows:
        return history_rows

    merged = list(history_rows)

    existing = {
        str(r.get("time") or r.get("timestamp"))
        for r in merged
    }

    for row in intraday_rows:
        ts = str(row.get("time") or row.get("timestamp"))
        if ts not in existing:
            merged.append(row)
            existing.add(ts)

    merged.sort(key=lambda x: str(x.get("time") or x.get("timestamp")))
    return merged

