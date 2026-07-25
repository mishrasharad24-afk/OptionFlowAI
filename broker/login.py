import logging
import requests

from config.settings import BASE_URL, API_VERSION, LOGIN_URL
from config.credentials import API_KEY


logging.basicConfig(
    filename="logs/login.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)


class BrokerLogin:

    def __init__(self):
        self.access_token = None

    def login(self, otp):

        headers = {
            "X-Mirae-Version": API_VERSION,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        payload = {
            "api_key": API_KEY,
            "totp": otp.strip()
        }

        try:
            response = requests.post(
                BASE_URL + LOGIN_URL,
                headers=headers,
                data=payload,
                timeout=20
            )

            data = response.json()

            if data.get("status") != "success":
                logging.error(data)
                print(data)
                return None

            self.access_token = data["data"]["access_token"]

            logging.info("LOGIN SUCCESS")

            return self.access_token

        except Exception as e:
            logging.exception(str(e))
            print(e)
            return None
