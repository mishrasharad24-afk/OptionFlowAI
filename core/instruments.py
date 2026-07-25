from tradingapi_a.mconnect import MConnect

API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

with open("/home/ec2-user/OptionFlowAI/access_token.txt") as f:
    token = f.read().strip()

m = MConnect(api_key=API_KEY, access_Token=token)

resp = m.get_instruments()

print(type(resp))

if isinstance(resp, bytes):
    print(resp.decode("utf-8")[:2000])
else:
    print(resp)
