class BrokerSession:

    def __init__(self):
        self._access_token = None

    def set_token(self, token):
        self._access_token = token

    def get_token(self):
        return self._access_token

    def is_logged_in(self):
        return self._access_token is not None


session = BrokerSession()
