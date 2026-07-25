def register():
    return {
        "name": "Option Flow Engine",
        "version": "1.0",
        "status": "READY",
        "features": [
            "ATM Selection",
            "OI Analysis",
            "PCR",
            "Delta",
            "Gamma",
            "IV",
            "Buyer Seller Strength"
        ]
    }

class OptionFlowEngine:

    def __init__(self):
        self.entry_buffer_up = 2
        self.entry_buffer_down = -2

    def get_atm_strike(self, spot_price, strike_step):
        return round(spot_price / strike_step) * strike_step

    def get_entry_zone(self, atm):
        return {
            "buy_above": atm + self.entry_buffer_up,
            "sell_below": atm + self.entry_buffer_down
        }
    def update_spot(self, spot_price):
        self.spot_price = float(spot_price)
        return self.spot_price
    def get_live_atm(self, strike_step=50):
        return self.get_atm_strike(
            self.spot_price,
            strike_step,
        )

    def get_option_symbols(self, strike_step=50):
        atm = self.get_live_atm(strike_step)

        return {
            "ATM": atm,
            "CE": f"{atm}CE",
            "PE": f"{atm}PE",
        }

    def build_symbol(self, index_name="NIFTY", expiry="", option_type="CE", strike_step=50):
        atm = self.get_live_atm(strike_step)

        return {
            "index": index_name,
            "expiry": expiry,
            "strike": atm,
            "option_type": option_type,
            "symbol": f"{index_name} {expiry} {atm} {option_type}".strip(),
        }
