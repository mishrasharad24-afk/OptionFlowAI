from pathlib import Path

code = r'''from tradingapi_a.mconnect import MConnect
import json

API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="
TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"

# Known working expiries (new ones can be added here)
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

def get_option_chain(exchange="2", token="26000"):

    api = _api()

    for expiry in KNOWN_EXPIRIES:
        r = api.get_option_chain_data(
            exchange,
            expiry,
            token,
        )

        try:
            j = r.json()
        except Exception:
            continue

        if j.get("status") == "success" and j.get("data") is not None:
            print(f"Using expiry: {expiry}")
            return r.text

    return json.dumps({
        "status":"error",
        "message":"No working expiry found"
    })

if __name__ == "__main__":
    print(get_option_chain())
'''

Path("core/mstock_option_chain.py").write_text(
    code,
    encoding="utf-8"
)

print("✓ Resolver installed")
