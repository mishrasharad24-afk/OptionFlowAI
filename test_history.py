from datetime import datetime
from historical.multi_timeframe_research import (
    MConnect,
    API_KEY,
    TOKEN_FILE,
)

with open(TOKEN_FILE) as f:
    token = f.read().strip()

m = MConnect(api_key=API_KEY)
m.set_access_token(token)

today = datetime.now().strftime("%Y-%m-%d")

resp = m.get_historical_chart(
    "NSE",
    "26000",
    "5minute",
    today,
    today,
)

print("TYPE:", type(resp))

try:
    print(resp.json())
except Exception as e:
    print("ERROR:", e)
    print(resp)

