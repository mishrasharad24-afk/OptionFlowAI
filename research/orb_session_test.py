from historical_reader import HistoricalReader
from orb_session_builder import ORBSessionBuilder

reader = HistoricalReader()

candles = reader.load()

orb = ORBSessionBuilder()

orb.load(candles)

sessions = orb.build()

print("=" * 60)
print("ORB SESSION TEST")
print("=" * 60)

print("Trading Days :", len(sessions))
print()

days = sorted(sessions.keys())

first = days[0]

print("First Trading Day :", str(first))
print("ORB High :", sessions[first]["orb_high"])
print("ORB Low  :", sessions[first]["orb_low"])

print("=" * 60)

reader.close()
