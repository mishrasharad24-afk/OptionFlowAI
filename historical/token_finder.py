import requests

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
)

if r.status_code != 200:
    print(r.text)
    raise SystemExit

j = r.json()

if j.get("status") != "success":
    print(j)
    raise SystemExit

token = j["data"]["access_token"]

headers = {
    "X-Mirae-Version": "1",
    "Authorization": f"token {API_KEY}:{token}"
}

resp = requests.get(
    "https://api.mstock.trade/openapi/typea/instruments/scriptmaster",
    headers=headers
)

print("STATUS:", resp.status_code)
print("CONTENT:", resp.headers.get("content-type"))
print(resp.text[:1000])
with open("/tmp/instrument_master.csv", "w") as f:
    f.write(resp.text)

print("Saved to /tmp/instrument_master.csv")
