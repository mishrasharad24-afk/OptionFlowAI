import json
import os

FLOW_STATE_FILE = os.path.expanduser("~/OptionFlowAI/flow_state.json")


def save_flow_state(memory):
    data = {}

    for name, state in memory.items():
        data[name] = {
            "ce_avg": state.get("ce_avg", 0),
            "pe_avg": state.get("pe_avg", 0),
            "ce_flow_count": state.get("ce_flow_count", 0),
            "pe_flow_count": state.get("pe_flow_count", 0),
            "ce_entry_armed": state.get("ce_entry_armed", False),
            "pe_entry_armed": state.get("pe_entry_armed", False),
            "ce_arm_low": state.get("ce_arm_low", 0),
            "pe_arm_low": state.get("pe_arm_low", 0),
        "last_exit": state.get("last_exit", 0),

            "trade": state.get("trade"),
            "last_exit": state.get("last_exit", 0),
            "track_ce_symbol": state.get("track_ce_symbol"),
            "track_pe_symbol": state.get("track_pe_symbol"),
            "stable_direction": state.get("stable_direction", "NEUTRAL"),
            "ce_history": state.get("ce_history", []),
            "pe_history": state.get("pe_history", []),
            "flow_prev": state.get("flow_prev", {}),
        }





    with open(FLOW_STATE_FILE, "w") as f:
        json.dump(data, f)


def load_flow_state(memory):
    if not os.path.exists(FLOW_STATE_FILE):
        return memory

    try:
        with open(FLOW_STATE_FILE, "r") as f:
            data = json.load(f)

        for name in data:
            if name in memory:
                memory[name].update(data[name])

    except Exception as e:
        print("[FLOW STATE]", e)

    return memory

