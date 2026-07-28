from core.mstock_option_chain import _api, token_to_symbol
import json

token = "65682"   # ATM CE token, बाद में बदल सकते हैं

info = token_to_symbol(token)

key = f'{info["exchange"]}:{info["symbol"]}'

api = _api()

r = api.get_ltp([key])

if hasattr(r, "json"):
    r = r.json()

print(json.dumps(r, indent=2))

