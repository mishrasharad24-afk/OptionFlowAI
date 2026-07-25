import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rest_client import RestClient

client = RestClient()

try:
    # SENSEX
    # Exchange Type: 4 = BSE
    # Token: 51
    # Interval: minute
    endpoint = "instruments/intraday/4/51/minute"

    response = client.get(endpoint)

    print("TEST:", endpoint)
    print("STATUS:", response.status_code)
    print(response.text)

except Exception as e:
    print("ERROR:", e)
