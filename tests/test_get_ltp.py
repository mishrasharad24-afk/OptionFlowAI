import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.mstock_quote_api import MStockQuoteAPI

api = MStockQuoteAPI()

print("=" * 60)
print("TEST GET LTP")
print("=" * 60)

result = api.get_ltp(["BSE:SENSEX"])

print(result)

print("=" * 60)
