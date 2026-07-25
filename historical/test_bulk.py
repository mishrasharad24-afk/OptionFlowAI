from broker.login import BrokerLogin
from broker.session import session
from historical.bulk_downloader import BulkDownloader


def main():

    otp = input("Enter m.Stock OTP: ").strip()

    broker = BrokerLogin()
    token = broker.login(otp)

    if not token:
        print("Login Failed")
        return

    session.set_token(token)

    downloader = BulkDownloader()

    downloader.download(
        exchange="BSE",
        token="51",
        symbol="SENSEX",
        timeframe="5minute",
        days=5
    )


if __name__ == "__main__":
    main()
