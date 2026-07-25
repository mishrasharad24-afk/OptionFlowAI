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

    DOWNLOAD_LIST = [

        {
            "exchange": "BSE",
            "token": "51",
            "symbol": "SENSEX",
            "timeframe": "5minute",
            "days": 365,
            "end_date": "2024-08-02"
        }

    ]

    for item in DOWNLOAD_LIST:

        print("=" * 70)
        print("Downloading :", item["symbol"])
        print("=" * 70)

        downloader.download(
            exchange=item["exchange"],
            token=item["token"],
            symbol=item["symbol"],
            timeframe=item["timeframe"],
            end_date=item["end_date"],
            days=item["days"]
        )


if __name__ == "__main__":
    main()
