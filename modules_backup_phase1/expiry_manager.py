def register():
    return {
        "name": "expiry_manager",
        "version": "1.0"
    }


class ExpiryManager:

    def __init__(self):
        self.expiries = []

    def update(self, expiry_list):
        self.expiries = sorted(expiry_list)

    def get_nearest(self):
        if not self.expiries:
            return None
        return self.expiries[0]
