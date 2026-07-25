import json

from final_ai_decision_engine_v2 import (
    run_historical_research,
    build_historical_edge_database,
)

CACHE_FILE = "ai_edge_cache.json"

print("STARTING HISTORICAL AI EDGE RESEARCH...")

combined_results = run_historical_research()

if not combined_results:
    raise SystemExit("ERROR: No historical research results")

edge_db = build_historical_edge_database(
    combined_results
)

records = edge_db.records

if not records:
    raise SystemExit("ERROR: No AI edge records generated")

with open(CACHE_FILE, "w") as f:
    json.dump(
        records,
        f,
        indent=2,
        default=str,
    )

print("=" * 60)
print("AI EDGE CACHE CREATED")
print("FILE    :", CACHE_FILE)
print("RECORDS :", len(records))
print("=" * 60)
