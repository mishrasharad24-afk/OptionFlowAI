class EMAFeatures:

    @staticmethod
    def side(price, ema):

        if price > ema:
            return "ABOVE"

        if price < ema:
            return "BELOW"

        return "ON"

    @staticmethod
    def alignment(ema20, ema50):

        if ema20 > ema50:
            return "BULL"

        if ema20 < ema50:
            return "BEAR"

        return "SIDE"
