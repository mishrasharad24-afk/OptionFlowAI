import requests

from broker.session import session
from config.settings import BASE_URL, API_VERSION


class HistoricalDownloader:

    def __init__(self):
        self.token = session.get_token()

    def is_ready(self):
        if not self.token:
            print("❌ No Access Token")
            return False
        return True

    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Mirae-Version": API_VERSION,
            "Content-Type": "application/json"
        }

    def download(self, segment_id, symbol, interval):

        if not self.is_ready():
            return None

        url = (
            f"{BASE_URL}/instruments/intraday/"
            f"{segment_id}/{symbol}/{interval}"
        )

        try:
            response = requests.get(
                url,
                headers=self.headers(),
                timeout=30
            )

            print("HTTP Status :", response.status_code)

            if response.status_code != 200:
                print(response.text)
                return None

            return response.text

        except Exception as e:
            print("Download Error :", e)
            return None
