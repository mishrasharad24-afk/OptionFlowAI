from core.mstock_option_chain import _load_chain
import json

data = _load_chain()

print(json.dumps(data, indent=2))

