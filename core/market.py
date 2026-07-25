import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingapi_a.mconnect import MConnect
from config.settings import *

with open(TOKEN_FILE, "r") as f:
    ACCESS_TOKEN = f.read().strip()

m = MConnect(
    api_key=API_KEY,
    access_Token=ACCESS_TOKEN
)

symbols = [
    "NSE:NIFTY 50",
    "NSE:NIFTY BANK",

    # SENSEX Symbol Tests
    "BSE:SENSEX",
    "BSE:SENSEX 30",
    "BSE:S&P BSE SENSEX"
]

try:

    resp = m.get_ltp(symbols)

    print(json.dumps(json.loads(resp.text), indent=4))

except Exception as e:
    print(e)
