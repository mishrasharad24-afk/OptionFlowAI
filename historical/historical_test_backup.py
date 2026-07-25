import requests
from datetime import datetime, timedelta

BASE_URL = "https://api.mstock.trade"

class HistoricalCollector:

    def __init__(self):
        print("Historical Collector Initialized")

    def fetch(self):
        print("Historical Fetch Started")

if __name__ == "__main__":
    collector = HistoricalCollector()
    collector.fetch()
