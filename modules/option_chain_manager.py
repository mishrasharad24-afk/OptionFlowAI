from core.mstock_option_chain import get_option_chain
from datetime import datetime
import json


def register():
    return {
        "name": "option_chain_manager",
        "version": "1.1"
    }


class OptionChainManager:

    def __init__(self):
        self.chain = []
        self.last_update = None

    def update(self, chain_data):
        self.chain = chain_data
        self.last_update = datetime.now()

    def get_chain(self):
        return self.chain

    def get_last_update(self):
        return self.last_update

    def clear(self):
        self.chain = []
        self.last_update = None

    def fetch_chain(
        self,
        exchange="2",
        token="26000",
        count="22",
    ):
        raw = get_option_chain(
            exchange,
            token,
            count,
        )

        try:
            data = json.loads(raw)
        except Exception:
            data = raw

        self.update(data)
        return data
