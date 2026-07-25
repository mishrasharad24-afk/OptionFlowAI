import requests

from broker.session import session
from config.settings import BASE_URL, API_VERSION
from config.credentials import API_KEY


class MarketClient:

    def __init__(self):
        self.token = session.get_token()

    def headers(self):

        if not self.token:
            raise RuntimeError("Access Token not available.")

        return {
            "Authorization": f"token {API_KEY}:{self.token}",
            "X-Mirae-Version": API_VERSION
        }

    def get(self, endpoint, params=None):

        url = f"{BASE_URL}{endpoint}"

        response = requests.get(
            url,
            headers=self.headers(),
            params=params,
            timeout=30
        )

        response.raise_for_status()

        return response
