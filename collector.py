import requests

from config.settings import BASE_URL
from config.credentials import API_KEY


class HistoricalCollector:

    def __init__(self, access_token):
        self.token = access_token

    def headers(self):
        return {
            "X-Mirae-Version": "1",
            "Authorization": f"token {API_KEY}:{self.token}"
        }

    def test_connection(self):

        url = BASE_URL + "/openapi/typea/instruments/scriptmaster"

        r = requests.get(
            url,
            headers=self.headers(),
            timeout=30
        )

        print("HTTP:", r.status_code)
        print("Content-Type:", r.headers.get("content-type"))

        return r
