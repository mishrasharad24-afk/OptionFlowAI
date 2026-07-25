import requests
from tradingapi_a.mconnect import MConnect

API_KEY = "tCEplvPZd+y8Ki7Dr5S7qtZr8QO3Tb+uQkgjKcGZdtc="

otp = input("Enter mStock TOTP: ")

r = requests.post(
    "https://api.mstock.trade/openapi/typea/session/verifytotp",
    headers={
        "X-Mirae-Version": "1",
        "Content-Type": "application/x-www-form-urlencoded"
    },
    data={
        "api_key": API_KEY,
        "totp": otp
    }
).json()

if r.get("status") != "success":
    print("LOGIN FAILED")
    print(r)
    raise SystemExit

token = r["data"]["access_token"]

api = MConnect(api_key=API_KEY)
api.set_access_token(token)

print("Getting Instrument Master...")

resp = api.get_instruments()

print("Response type:", type(resp))

try:
    print(resp.json())
except Exception:
    print(resp.text)
