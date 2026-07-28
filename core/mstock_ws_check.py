import tradingapi_a
import inspect
import tradingapi_a.mconnect as m

print("tradingapi_a:", tradingapi_a.__file__)
print("=" * 60)

for name, obj in inspect.getmembers(m.MConnect):
    if "ws" in name.lower() or "socket" in name.lower() or "stream" in name.lower() or "feed" in name.lower():
        print(name)

