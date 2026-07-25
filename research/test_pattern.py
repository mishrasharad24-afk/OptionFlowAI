from research.pattern_engine import PatternEngine

engine = PatternEngine()

engine.research(
    symbol="SENSEX",
    timeframe="5minute"
)

engine.close()
