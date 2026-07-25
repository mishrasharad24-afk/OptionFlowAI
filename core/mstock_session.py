from tradingapi_a.mconnect import MConnect
import hashlib
import pyotp


class MStockSession:

    def __init__(
        self,
        user_id,
        password,
        api_key,
        secret_key,
        totp_secret
    ):

        self.user_id = user_id
        self.password = password
        self.api_key = api_key
        self.secret_key = secret_key
        self.totp_secret = totp_secret

        self.client = MConnect()

    def login(self):

        print("=" * 60)
        print("MSTOCK SESSION")
        print("=" * 60)

        login = self.client.login(
            self.user_id,
            self.password
        )

        print(login)

        request_token = input(
            "Enter Request Token : "
        )

        checksum = hashlib.sha256(
            (
                self.api_key +
                self.secret_key +
                request_token
            ).encode()
        ).hexdigest()

        session = self.client.generate_session(
            self.api_key,
            request_token,
            checksum
        )

        print(session)

        totp = pyotp.TOTP(
            self.totp_secret
        ).now()

        verify = self.client.verify_totp(
            self.api_key,
            totp
        )

        print(verify)

        print()
        print("LOGIN SUCCESS")
        print("=" * 60)

        return self.client
