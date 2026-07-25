import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rest_client import RestClient

client = RestClient()

try:
    response = client.get("instruments/intraday/1/26000/minute")
    print("Status:", response.status_code)
    print(response.text)
except Exception as e:
    print("ERROR:", e)
