from tradingapi_a.mconnect import MConnect

API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

with open("/home/ec2-user/OptionFlowAI/access_token.txt", "r") as f:
    ACCESS_TOKEN = f.read().strip()

m = MConnect(
    api_key=API_KEY,
    access_Token=ACCESS_TOKEN
)
print("API KEY =", m.api_key)
print("TOKEN =", m.access_token[:25])
try:
    response = m.get_ltp(["NSE:NIFTY 50"])
    print(response.text)
except Exception as e:
    print(e)
