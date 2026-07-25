from historical.curve_option_backtest import MConnect, API_KEY, TOKEN_FILE
from pathlib import Path

token = Path(TOKEN_FILE).read_text().strip()

m = MConnect(
    api_key=API_KEY,
    access_Token=token,
)

try:
    resp = m.get_historical_chart(
        "NFO",
        "38055",
        "5minute",
        "2026-07-14",
        "2026-07-14",
    )
    print(resp.status_code)
    print(resp.text)

except Exception:
    import traceback
    traceback.print_exc()
