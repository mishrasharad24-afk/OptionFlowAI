class DayClassifier:

    def classify(self, features):

        direction = features["direction"]
        day_range = features["range"]

        if direction == "BULLISH":

            if day_range >= 400:
                return "TREND_UP"

            return "UP"

        if direction == "BEARISH":

            if day_range >= 400:
                return "TREND_DOWN"

            return "DOWN"

        return "SIDEWAYS"
