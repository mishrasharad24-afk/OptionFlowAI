import requests


class TelegramSender:

    def __init__(self, bot_token, chat_id):

        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, message):

        url = (
            f"https://api.telegram.org/bot"
            f"{self.bot_token}/sendMessage"
        )

        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:

            response = requests.post(
                url,
                data=data,
                timeout=10
            )

            return response.json()

        except Exception as e:

            return {
                "status": "error",
                "message": str(e)
            }


if __name__ == "__main__":

    print("=" * 60)
    print("TELEGRAM SENDER READY")
    print("=" * 60)
    print()
    print("Import this module from AI Engine.")
    print()
    print("=" * 60)
