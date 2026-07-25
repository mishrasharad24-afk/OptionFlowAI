from research.pattern_engine import PatternEngine
from research.day_classifier import DayClassifier


class ResearchEngine:

    def __init__(self):

        self.pattern = PatternEngine()
        self.classifier = DayClassifier()

    def analyze(self, symbol, timeframe):

        features = self.pattern.research(symbol, timeframe)

        if not features:
            return None

        day_type = self.classifier.classify(features)

        print("=" * 50)
        print("AI RESEARCH RESULT")
        print("=" * 50)
        print("Day Type :", day_type)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "day_type": day_type,
            "features": features
        }

    def close(self):

        self.pattern.close()
