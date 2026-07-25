from tradingapi_a.mconnect import MConnect
import json

API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

with open("/home/ec2-user/OptionFlowAI/access_token.txt") as f:
    access_token = f.read().strip()

api = MConnect(
    api_key=API_KEY,
    access_Token=access_token
)

resp = api.get_option_chain_master("2")

print(resp.status_code)
print(json.dumps(resp.json(), indent=2))
resp = api.get_option_chain_data(
    "2",
    "1470321000",   # dctExp का timestamp
    "26000"         # NIFTY token
)

print(resp.status_code)
print(resp.text)
