import requests

API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

TOKEN_FILE = "/home/ec2-user/OptionFlowAI/access_token.txt"


class RestClient:

    def __init__(self):
        with open(TOKEN_FILE, "r") as f:
            self.access_token = f.read().strip()

        self.base_url = "https://api.mstock.trade/openapi/typea/"

        self.headers = {
            "Authorization": f"token {API_KEY}:{self.access_token}",
            "X-Mirae-Version": "1",
            "Content-Type": "application/json"
        }

    def get(self, endpoint):

        url = self.base_url + endpoint

        response = requests.get(
            url,
            headers=self.headers,
            verify=False,
            timeout=15
        )

        return response

    def post(self, endpoint, payload):

        url = self.base_url + endpoint

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            verify=False,
            timeout=15
        )

        return response
