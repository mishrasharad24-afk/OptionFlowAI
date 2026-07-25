import requests
import time
import csv
from datetime import datetime, date

from live_market_candle_engine import LiveMarketCandleEngine
from ai_live_bridge import build_live_spot_context
from final_ai_decision_engine_v2 import (
    load_ai_edge_cache,
    make_ai_decision,
)
from historical.indicator_combination_research import load_api
from core.option_selector import select_atm_options
from core.option_market_data import OptionMarketData


# ===== CONFIG =====

API_KEY = "0I9xsJEBJ+a0Gc5iw7Fz7PGU153rvhvaOdUUoA01lC0="

BOT_TOKEN = "7705146253:AAGpL1cyzqL6_afWFGdrXGAU5M0Ku1VCFVM"
CHAT_ID = "-1002519123618"

MASTER="/home/ec2-user/pytradingapi-typeA/mock_responses/instrument_scrip_master.csv"


# ===== TELEGRAM =====

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id":CHAT_ID,
                "text":msg
            }
        )
    except:
        pass



# ===== SAVED TOKEN LOAD =====

def login():
    try:
        token_file = "/home/ec2-user/OptionFlowAI/access_token.txt"

        with open(token_file, "r") as f:
            token = f.read().strip()

        if not token:
            print("ACCESS TOKEN FILE EMPTY")
            return None

        print("SAVED ACCESS TOKEN LOADED")
        return token

    except Exception as e:
        print(
            "TOKEN LOAD FAILED:",
            type(e).__name__,
            e
        )
        return None


# ===== MASTER READ =====

def load_master(index):

    arr=[]

    with open(MASTER) as f:

        rd=csv.reader(f)

        for r in rd:

            try:

                sym=r[2]
                exp=r[5]
                strike=float(r[6])
                side=r[9]
                typ=r[10]


                if typ!="OPTIDX":
                    continue


                if index=="NIFTY":

                    if not sym.startswith("NIFTY"):
                        continue

                    if "BANK" in sym or "NXT" in sym:
                        continue



                if index=="SENSEX":

                    if not sym.startswith("SENSEX"):
                        continue



                expd=datetime.strptime(
                    exp,"%Y-%m-%d"
                ).date()


                if expd < date.today():
                    continue



                # m.Stock LTP API requires EXCHANGE:tradingsymbol
                exchange = r[11].strip()

                arr.append({
                    "symbol": f"{exchange}:{sym}",
                    "expiry": expd,
                    "strike": strike,
                    "side": side
                })


            except:
                pass


    return arr




# ===== LTP =====

def ltp(headers,symbol):

    try:

        r=requests.get(
            "https://api.mstock.trade/openapi/typea/instruments/quote/ltp",
            headers=headers,
            params={"i":symbol}
        ).json()


        return float(
            list(r["data"].values())[0]["last_price"]
        )


    except:

        return None# ===== ATM FIND =====

def find_atm(options,spot):

    if not options:
        return None,None

    expiry=min(
        x["expiry"] for x in options
    )

    live=[
        x for x in options
        if x["expiry"]==expiry
    ]


    atm=min(
        live,
        key=lambda x:abs(x["strike"]-spot)
    )["strike"]


    ce=None
    pe=None


    for x in live:

        if x["strike"]==atm:

            if x["side"]=="CE":
                ce=x["symbol"]

            if x["side"]=="PE":
                pe=x["symbol"]


    return ce,pe



# ===== ATM +/-2 FLOW =====

def find_atm_flow(options,spot):

    if not options:
        return [],[]

    expiry=min(x["expiry"] for x in options)

    live=[
        x for x in options
        if x["expiry"]==expiry
    ]

    atm=min(
        live,
        key=lambda x:abs(x["strike"]-spot)
    )["strike"]

    strikes=sorted(
        list(set(x["strike"] for x in live))
    )

    pos=strikes.index(atm)

    use=strikes[
        max(0,pos-2):pos+3
    ]

    ce=[]
    pe=[]

    for x in live:
        if x["strike"] in use:
            if x["side"]=="CE":
                ce.append(x["symbol"])
            if x["side"]=="PE":
                pe.append(x["symbol"])

    return ce,pe

# ===== LIVE ATM OPTION 3-CANDLE CONFIRMATION =====
def get_option_confirmation(option_market, index_name, spot, ai_action):
    """
    Current nearest-expiry ATM option confirmation.

    CE action -> ATM CE option checked
    PE action -> ATM PE option checked

    CONFIRMED when at least 2 of latest 3 available
    option candles are bullish.
    """
    result = {
        "confirmed": False,
        "score": 0,
        "symbol": None,
        "token": None,
        "reason": "NOT_CHECKED",
    }

    if ai_action not in ("CE", "PE"):
        result["reason"] = "AI_WAIT"
        return result

    try:
        selected = select_atm_options(index_name, spot)

        if not selected:
            result["reason"] = "NO_ATM_OPTION"
            return result

        key = ai_action.lower()
        contract = selected.get(key)

        if not contract:
            result["reason"] = "CONTRACT_NOT_FOUND"
            return result

        result["symbol"] = contract.get("symbol")
        result["token"] = contract.get("token")

        data = option_market.get_option_candles(
            index_name,
            contract["token"],
        )

        candles = (
            data.get("data", {}).get("candles", [])
            if isinstance(data, dict)
            else []
        )

        if len(candles) < 3:
            result["reason"] = "LESS_THAN_3_CANDLES"
            return result

        # API normally returns newest candle first.
        # We only need the latest 3 available candles.
        latest_three = candles[:3]

        bullish = 0

        for candle in latest_three:
            try:
                o = float(candle[1])
                c = float(candle[4])

                if c > o:
                    bullish += 1

            except Exception:
                continue

        result["score"] = bullish
        result["confirmed"] = bullish >= 2
        result["reason"] = (
            "OPTION_2_OF_3_BULLISH"
            if result["confirmed"]
            else "OPTION_NOT_CONFIRMED"
        )

        return result

    except Exception as e:
        result["reason"] = (
            f"OPTION_CONFIRM_ERROR:"
            f"{type(e).__name__}"
        )
        return result


# ===== OPTION FIGHT ENGINE =====

def scanner(token):

    # ===== LIVE AI ENGINE INIT =====
    live_candle_engine = LiveMarketCandleEngine()
    ai_edge_db = load_ai_edge_cache()
    historical_api = load_api()

    # ===== LIVE OPTION CONFIRMATION ENGINE INIT =====
    option_market = OptionMarketData()

    print("LIVE AI OBSERVATION ENGINE READY")
    print("LIVE ATM OPTION CONFIRMATION ENGINE READY")
    send("🤖 LIVE AI ENGINE READY\n5M + 15M CANDLE ENGINE ACTIVE\nAI OBSERVATION MODE ON")


    headers={
        "X-Mirae-Version":"1",
        "Authorization":f"token {API_KEY}:{token}"
    }


    send("🚀 OPTION FIGHT ENGINE START")


    data={
        "NIFTY":load_master("NIFTY"),
        "SENSEX":load_master("SENSEX")
    }


    memory={
        "NIFTY":{
            "trade":None,
            "last_exit":0,
            "dir_candidate":"NEUTRAL",
            "dir_count":0,
            "dir_candidate_since":0,
            "stable_direction":"NEUTRAL",
            "ce":0,
            "pe":0,
            "ce_avg":0,
            "pe_avg":0,
            "ce_flow_count":0,
            "pe_flow_count":0,
            "track_ce_symbol":None,
            "track_pe_symbol":None,
            "ce_history":[],
            "pe_history":[],
            "ce_entry_armed":False,
            "pe_entry_armed":False,
            "ce_arm_low":0,
            "pe_arm_low":0,
            "entry_price":0,
            "trade_symbol":None,
            "trade_high":0,
            "dynamic_sl":0,
            "last_exit_side":None,
            "last_exit_reason":None,
            "reentry_count":0,
            "sl_hit_count":0,
            "flow_prev":{}
        },

        "SENSEX":{
            "trade":None,
            "last_exit":0,
            "dir_candidate":"NEUTRAL",
            "dir_count":0,
            "dir_candidate_since":0,
            "stable_direction":"NEUTRAL",
            "ce":0,
            "pe":0,
            "ce_avg":0,
            "pe_avg":0,
            "ce_flow_count":0,
            "pe_flow_count":0,
            "track_ce_symbol":None,
            "track_pe_symbol":None,
            "ce_history":[],
            "pe_history":[],
            "ce_entry_armed":False,
            "pe_entry_armed":False,
            "ce_arm_low":0,
            "pe_arm_low":0,
            "entry_price":0,
            "trade_symbol":None,
            "trade_high":0,
            "dynamic_sl":0,
            "last_exit_side":None,
            "last_exit_reason":None,
            "reentry_count":0,
            "sl_hit_count":0,
            "flow_prev":{}
        }
    }



    while True:


        now=datetime.now().strftime("%H:%M")


        if now < "09:15":

            time.sleep(20)
            continue



        if now >= "15:30":

            send("🛑 3:30 PM BOT CLOSED")

            break



        for name in ["NIFTY","SENSEX"]:

            # ===== SAFE AI STATE =====
            ai_action = "WAIT"
            ai_direction = "NEUTRAL"
            stable_direction = memory[name].get(
                "stable_direction",
                "NEUTRAL"
            )
            ai_score = 0.0
            ai_confidence = "LOW"
            ai_setup = "NO_VALID_COMBINATION"



            spot_symbol = (
                "NSE:NIFTY 50"
                if name=="NIFTY"
                else
                "BSE:SENSEX"
            )


            spot=ltp(headers,spot_symbol)


            if not spot:
                continue

            # ===== LIVE AI OBSERVATION MODE =====
            try:
                live_candles = live_candle_engine.update(
                    spot_symbol,
                    spot,
                )

                ai_context = build_live_spot_context(
                    historical_api,
                    name,
                    live_5m=live_candles["current_5m"],
                    live_15m=live_candles["current_15m"],
                )

                if ai_context.get("valid"):

                    ai_decision = make_ai_decision(
                        edge_db=ai_edge_db,
                        regime=ai_context["regime"],
                        direction=ai_context["direction"],
                        combination=ai_context["combination"],
                        current_price=spot,
                    )

                    ai_action = ai_decision.get("action", "WAIT")
                    ai_direction = ai_context.get("direction", "NEUTRAL")

                    # ===== 60-SECOND STABLE AI DIRECTION =====
                    if ai_direction in ("BULLISH", "BEARISH"):

                        if memory[name].get("dir_candidate") != ai_direction:
                            memory[name]["dir_candidate"] = ai_direction
                            memory[name]["dir_candidate_since"] = time.time()
                            memory[name]["dir_count"] = 1
                        else:
                            memory[name]["dir_count"] += 1

                        if (
                            memory[name].get("dir_candidate_since", 0) > 0
                            and time.time() - memory[name]["dir_candidate_since"] >= 60
                        ):
                            memory[name]["stable_direction"] = ai_direction

                    stable_direction = memory[name]["stable_direction"]

                    ai_score = ai_decision.get("ai_score", 0.0)
                    ai_confidence = ai_decision.get("confidence", "LOW")
                    ai_setup = ai_context.get(
                        "combination",
                        "NO_VALID_COMBINATION"
                    )

                    print(
                        "[AI OBSERVE]",
                        name,
                        "| PRICE", spot,
                        "| REGIME", ai_context["regime"],
                        "| DIR", ai_context["direction"],
                        "| ACTION", ai_decision.get("action"),
                        "| SCORE", round(
                            ai_decision.get("ai_score", 0),
                            2
                        ),
                        "| CONF", ai_decision.get("confidence"),
                        "| SETUP", ai_context["combination"],
                    )

                else:
                    print(
                        "[AI OBSERVE]",
                        name,
                        "| PRICE", spot,
                        "| ACTION WAIT",
                        "| REASON NO_VALID_LIVE_SETUP",
                    )

            except Exception as e:
                print(
                    "[AI OBSERVE ERROR]",
                    name,
                    type(e).__name__,
                    e,
                )



            


            # ===== LIVE ATM OPTION CONFIRMATION OBSERVATION =====
            option_confirmation = get_option_confirmation(
                option_market,
                name,
                spot,
                ai_action,
            )

            print(
                "[OPTION CONFIRM]",
                name,
                "| AI", ai_action,
                "| SYMBOL", option_confirmation.get("symbol"),
                "| SCORE", f'{option_confirmation.get("score", 0)}/3',
                "| CONFIRMED", option_confirmation.get("confirmed"),
                "| REASON", option_confirmation.get("reason"),
            )

            ce,pe=find_atm(
                data[name],
                spot
            )

            print(
                "[ATM SELECT]",
                name,
                "| SPOT", spot,
                "| CE", ce,
                "| PE", pe,
            )


            if not ce or not pe:
                print("[FLOW SKIP]", name, "| REASON ATM_NOT_FOUND", "| SPOT", spot, "| CE", ce, "| PE", pe)
                continue




            ce_ltp=ltp(headers,ce)

            pe_ltp=ltp(headers,pe)


            if not ce_ltp or not pe_ltp:
                print("[FLOW SKIP]", name, "| REASON OPTION_LTP_MISSING", "| CE", ce, ce_ltp, "| PE", pe, pe_ltp)
                continue

            # ===== 3-MINUTE PREMIUM HISTORY / NO-CHASE TRACKING =====
            # Reset history whenever ATM option symbol changes
            if memory[name].get("track_ce_symbol") != ce:
                memory[name]["track_ce_symbol"] = ce
                memory[name]["ce_history"] = []

            if memory[name].get("track_pe_symbol") != pe:
                memory[name]["track_pe_symbol"] = pe
                memory[name]["pe_history"] = []

            memory[name]["ce_history"].append(ce_ltp)
            memory[name]["pe_history"].append(pe_ltp)

            # Approx 3 minutes at 5-second loop
            memory[name]["ce_history"] = memory[name]["ce_history"][-36:]
            memory[name]["pe_history"] = memory[name]["pe_history"][-36:]

            ce_recent_low = min(memory[name]["ce_history"])
            pe_recent_low = min(memory[name]["pe_history"])

            ce_run_pct = ((ce_ltp - ce_recent_low) / ce_recent_low) * 100 if ce_recent_low else 0
            pe_run_pct = ((pe_ltp - pe_recent_low) / pe_recent_low) * 100 if pe_recent_low else 0

            # ===== NO-CHASE + LATE-SPIKE FILTER =====
            # Existing 3-minute expansion filter
            ce_no_chase = ce_run_pct <= 40
            pe_no_chase = pe_run_pct <= 40

            # Approx 60-second reference (12 cycles x 5 sec)
            ce_60s_ref = (
                memory[name]["ce_history"][-12]
                if len(memory[name]["ce_history"]) >= 12
                else ce_ltp
            )

            pe_60s_ref = (
                memory[name]["pe_history"][-12]
                if len(memory[name]["pe_history"]) >= 12
                else pe_ltp
            )

            ce_spike_pct = (
                ((ce_ltp - ce_60s_ref) / ce_60s_ref) * 100
                if ce_60s_ref else 0
            )

            pe_spike_pct = (
                ((pe_ltp - pe_60s_ref) / pe_60s_ref) * 100
                if pe_60s_ref else 0
            )

            # Block fresh BUY after >15% vertical move in ~60 seconds
            ce_late_spike_ok = ce_spike_pct <= 15
            pe_late_spike_ok = pe_spike_pct <= 15

            ce_no_chase = ce_no_chase and ce_late_spike_ok
            pe_no_chase = pe_no_chase and pe_late_spike_ok

            print(
                "[NO CHASE]",
                name,
                "| CE_RUN", round(ce_run_pct, 2),
                "| PE_RUN", round(pe_run_pct, 2),
                "| CE_SPIKE60", round(ce_spike_pct, 2),
                "| PE_SPIKE60", round(pe_spike_pct, 2),
                "| CE_OK", ce_no_chase,
                "| PE_OK", pe_no_chase,
            )

            old_ce=memory[name]["ce"]
            old_pe=memory[name]["pe"]


            memory[name]["ce"]=ce_ltp
            memory[name]["pe"]=pe_ltp
            ce_score=0
            pe_score=0


            if old_ce==0:
                print("[FLOW INIT]", name, "| CE", ce_ltp, "| PE", pe_ltp)
                continue



            ce_move=((ce_ltp-old_ce)/old_ce)*100

            pe_move=((pe_ltp-old_pe)/old_pe)*100

            # PREMIUM RUNNING AVERAGE
            if memory[name]["ce_avg"]==0:
                memory[name]["ce_avg"]=ce_ltp

            if memory[name]["pe_avg"]==0:
                memory[name]["pe_avg"]=pe_ltp


            memory[name]["ce_avg"]=(memory[name]["ce_avg"]*9+ce_ltp)/10

            memory[name]["pe_avg"]=(memory[name]["pe_avg"]*9+pe_ltp)/10


            if ce_ltp > memory[name]["ce_avg"]:
                ce_score+=20

            if pe_ltp > memory[name]["pe_avg"]:
                pe_score+=20

                        # ===== ATM +/-2 FLOW SCORE =====
            flow_ce,flow_pe=find_atm_flow(
                data[name],
                spot
            )

            # ===== REAL MULTI-STRIKE PREMIUM FLOW =====
            # Compare each option with ITS OWN previous LTP.
            # Do not compare different strikes by absolute premium.

            ce_power = 0
            pe_power = 0
            ce_falling = 0
            pe_falling = 0

            flow_prev = memory[name].setdefault("flow_prev", {})

            for sym in flow_ce:
                p = ltp(headers, sym)

                if p:
                    prev = flow_prev.get(sym)

                    if prev and prev > 0:
                        move = ((p - prev) / prev) * 100

                        if move > 0.20:
                            ce_power += 1
                        elif move < -0.20:
                            ce_falling += 1

                    flow_prev[sym] = p

            for sym in flow_pe:
                p = ltp(headers, sym)

                if p:
                    prev = flow_prev.get(sym)

                    if prev and prev > 0:
                        move = ((p - prev) / prev) * 100

                        if move > 0.20:
                            pe_power += 1
                        elif move < -0.20:
                            pe_falling += 1

                    flow_prev[sym] = p

            # Strong directional breadth:
            # own side rising across 3+ strikes
            # AND opposite side weakening across 2+ strikes
            if ce_power >= 3 and pe_falling >= 2:
                ce_score += 50

            if pe_power >= 3 and ce_falling >= 2:
                pe_score += 50
            if ce_move>2:
                ce_score+=50

            if pe_move<-1:
                ce_score+=30



            if pe_move>2:
                pe_score+=50

            if ce_move<-1:
                pe_score+=30


            # ===== LIVE FLOW SCORE DEBUG =====
            print(
                "[FLOW DEBUG]",
                name,
                "| SPOT", spot,
                "| CE", ce_ltp,
                "| PE", pe_ltp,
                "| CE_MOVE", round(ce_move, 2),
                "| PE_MOVE", round(pe_move, 2),
                "| CE_POWER", ce_power,
                "| PE_POWER", pe_power,
                "| CE_FALL", ce_falling,
                "| PE_FALL", pe_falling,
                "| CE_AVG", round(memory[name]["ce_avg"], 2),
                "| PE_AVG", round(memory[name]["pe_avg"], 2),
                "| CE_SCORE", ce_score,
                "| PE_SCORE", pe_score,
            )


            # ===== 3-CYCLE FLOW CONFIRMATION =====
            # Strong flow must persist for 3 consecutive cycles.
            # A weak cycle resets that side's confirmation count.

            if ce_score >= 70 and ce_move > 0:
                memory[name]["ce_flow_count"] += 1
            else:
                memory[name]["ce_flow_count"] = 0

            if pe_score >= 70 and pe_move > 0:
                memory[name]["pe_flow_count"] += 1
            else:
                memory[name]["pe_flow_count"] = 0

            # Normal entry: 3 consecutive strong-flow cycles
            ce_flow_confirmed = memory[name]["ce_flow_count"] >= 3
            pe_flow_confirmed = memory[name]["pe_flow_count"] >= 3

            # Fast-move entry: allow 2 cycles only when momentum is very strong
            ce_fast_confirmed = (
                memory[name]["ce_flow_count"] >= 2
                and ce_score >= 100
                and ce_move > 2
            )

            pe_fast_confirmed = (
                memory[name]["pe_flow_count"] >= 2
                and pe_score >= 100
                and pe_move > 2
            )

            ce_entry_confirmed = ce_flow_confirmed or ce_fast_confirmed
            pe_entry_confirmed = pe_flow_confirmed or pe_fast_confirmed

            print(
                "[FLOW CONFIRM]",
                name,
                "| CE_COUNT", memory[name]["ce_flow_count"],
                "| PE_COUNT", memory[name]["pe_flow_count"],
                "| CE_OK", ce_flow_confirmed,
                "| PE_OK", pe_flow_confirmed,
            )

            # ===== SAFE TRADE STATE / PULLBACK ENTRY =====

            current_trade = memory[name]["trade"]

            # ===== MANUAL SL MODE =====
            # Dynamic premium SL disabled. User manages SL manually.
            dynamic_sl_exit = False


            if current_trade == "CE" and pe_flow_confirmed and ai_direction == "BEARISH" and stable_direction == "BEARISH":
                print("[EXIT DEBUG]", name, "| TRADE CE | CE_SCORE", ce_score, "| PE_SCORE", pe_score, "| AI_DIR", ai_direction)
                send(
                    f"⚠️ EXIT {name} CE\n"
                    f"REASON: PE FLOW {pe_score} + STABLE AI {stable_direction}\n"
                    f"CE SCORE: {ce_score} | PE SCORE: {pe_score}\n"
                    f"COOLDOWN: 5 MIN"
                )
                memory[name]["trade"] = None
                memory[name]["trade_symbol"] = None
                memory[name]["last_exit"] = time.time()
                memory[name]["last_exit_side"] = "CE"
                memory[name]["last_exit_reason"] = "OPPOSITE_FLOW"
                memory[name]["entry_price"] = 0
                memory[name]["trade_high"] = 0
                memory[name]["dynamic_sl"] = 0
                memory[name]["sl_hit_count"] = 0
                memory[name]["ce_entry_armed"] = False
                memory[name]["pe_entry_armed"] = False

            elif current_trade == "PE" and ce_flow_confirmed and ai_direction == "BULLISH" and stable_direction == "BULLISH":
                print("[EXIT DEBUG]", name, "| TRADE PE | CE_SCORE", ce_score, "| PE_SCORE", pe_score, "| AI_DIR", ai_direction)
                send(
                    f"⚠️ EXIT {name} PE\n"
                    f"REASON: CE FLOW {ce_score} + STABLE AI {stable_direction}\n"
                    f"CE SCORE: {ce_score} | PE SCORE: {pe_score}\n"
                    f"COOLDOWN: 5 MIN"
                )
                memory[name]["trade"] = None
                memory[name]["trade_symbol"] = None
                memory[name]["last_exit"] = time.time()
                memory[name]["last_exit_side"] = "PE"
                memory[name]["last_exit_reason"] = "OPPOSITE_FLOW"
                memory[name]["entry_price"] = 0
                memory[name]["trade_high"] = 0
                memory[name]["dynamic_sl"] = 0
                memory[name]["sl_hit_count"] = 0
                memory[name]["ce_entry_armed"] = False
                memory[name]["pe_entry_armed"] = False

            # ===== ARM DIRECTION FIRST, DO NOT CHASE FIRST SIGNAL =====
            elif current_trade is None and (
                time.time() - memory[name].get("last_exit", 0) >= (
                    30
                    if memory[name].get("last_exit_reason") == "DYNAMIC_SL"
                    else 300
                )
            ):

                # CE direction/flow confirmed: arm and track lowest premium
                if (
                    ce_entry_confirmed
                    and ai_direction == "BULLISH"
                    and stable_direction == "BULLISH"
                ):
                    if not memory[name]["ce_entry_armed"]:
                        memory[name]["ce_entry_armed"] = True
                        memory[name]["ce_arm_low"] = ce_ltp
                        print("[ENTRY ARMED]", name, "CE", "| PRICE", ce_ltp)
                    else:
                        memory[name]["ce_arm_low"] = min(
                            memory[name]["ce_arm_low"], ce_ltp
                        )

                # PE direction/flow confirmed: arm and track lowest premium
                if (
                    pe_entry_confirmed
                    and ai_direction == "BEARISH"
                    and stable_direction == "BEARISH"
                ):
                    if not memory[name]["pe_entry_armed"]:
                        memory[name]["pe_entry_armed"] = True
                        memory[name]["pe_arm_low"] = pe_ltp
                        print("[ENTRY ARMED]", name, "PE", "| PRICE", pe_ltp)
                    else:
                        memory[name]["pe_arm_low"] = min(
                            memory[name]["pe_arm_low"], pe_ltp
                        )

                # Keep updating pullback low while direction remains aligned
                if memory[name]["ce_entry_armed"] and ai_direction == "BULLISH" and stable_direction == "BULLISH":
                    memory[name]["ce_arm_low"] = min(memory[name]["ce_arm_low"], ce_ltp)

                if memory[name]["pe_entry_armed"] and ai_direction == "BEARISH" and stable_direction == "BEARISH":
                    memory[name]["pe_arm_low"] = min(memory[name]["pe_arm_low"], pe_ltp)

                # Recovery trigger: premium must rise 3% from post-arm low
                ce_recovery = (
                    memory[name]["ce_entry_armed"]
                    and memory[name]["ce_arm_low"] > 0
                    and ce_ltp >= memory[name]["ce_arm_low"] * 1.03
                )

                pe_recovery = (
                    memory[name]["pe_entry_armed"]
                    and memory[name]["pe_arm_low"] > 0
                    and pe_ltp >= memory[name]["pe_arm_low"] * 1.03
                )

                print(
                    "[PULLBACK ENTRY]",
                    name,
                    "| CE_ARM", memory[name]["ce_entry_armed"],
                    "| CE_LOW", memory[name]["ce_arm_low"],
                    "| CE_RECOVERY", ce_recovery,
                    "| PE_ARM", memory[name]["pe_entry_armed"],
                    "| PE_LOW", memory[name]["pe_arm_low"],
                    "| PE_RECOVERY", pe_recovery,
                )

                if (
                    ce_recovery
                    and memory[name]["trade"] is None
                    and ce_no_chase
                    and ai_direction == "BULLISH"
                    and stable_direction == "BULLISH"
                ):
                    send(
                        f"🔥 {name} CE BUY SIGNAL\n"
                        f"STRIKE: {int(round(spot / (50 if name == 'NIFTY' else 100)) * (50 if name == 'NIFTY' else 100))} CE\n"
                        f"SYMBOL: {ce}\n"
                        f"PRICE: {ce_ltp}\n"
                        f"PULLBACK LOW: {memory[name]['ce_arm_low']:.2f}\n"
                        f"ENTRY TYPE: PULLBACK RECOVERY\n"
                        f"FLOW SCORE: {ce_score}\n"
                        f"AI DIR: {ai_direction}\n"
                        f"STABLE DIR: {stable_direction}\n"
                        f"AI ACTION: {ai_action}\n"
                        f"AI SCORE: {ai_score:.2f}\n"
                        f"CONF: {ai_confidence}\n"
                        f"SETUP: {ai_setup}"
                    )
                    is_reentry = (
                        memory[name].get("last_exit_side") == "CE"
                        and memory[name].get("last_exit_reason") == "DYNAMIC_SL"
                    )
                    memory[name]["trade"] = "CE"
                    memory[name]["trade_symbol"] = ce
                    memory[name]["entry_price"] = ce_ltp
                    memory[name]["trade_high"] = ce_ltp
                    memory[name]["dynamic_sl"] = ce_ltp * 0.92
                    memory[name]["sl_hit_count"] = 0
                    if is_reentry:
                        memory[name]["reentry_count"] += 1
                        print("[SAME SIDE RE-ENTRY]", name, "CE", "| PRICE", ce_ltp)
                    memory[name]["last_exit_side"] = None
                    memory[name]["last_exit_reason"] = None
                    memory[name]["ce_entry_armed"] = False

                elif (
                    pe_recovery
                    and memory[name]["trade"] is None
                    and pe_no_chase
                    and ai_direction == "BEARISH"
                    and stable_direction == "BEARISH"
                ):
                    send(
                        f"🔻 {name} PE BUY SIGNAL\n"
                        f"STRIKE: {int(round(spot / (50 if name == 'NIFTY' else 100)) * (50 if name == 'NIFTY' else 100))} PE\n"
                        f"SYMBOL: {pe}\n"
                        f"PRICE: {pe_ltp}\n"
                        f"PULLBACK LOW: {memory[name]['pe_arm_low']:.2f}\n"
                        f"ENTRY TYPE: PULLBACK RECOVERY\n"
                        f"FLOW SCORE: {pe_score}\n"
                        f"AI DIR: {ai_direction}\n"
                        f"STABLE DIR: {stable_direction}\n"
                        f"AI ACTION: {ai_action}\n"
                        f"AI SCORE: {ai_score:.2f}\n"
                        f"CONF: {ai_confidence}\n"
                        f"SETUP: {ai_setup}"
                    )
                    is_reentry = (
                        memory[name].get("last_exit_side") == "PE"
                        and memory[name].get("last_exit_reason") == "DYNAMIC_SL"
                    )
                    memory[name]["trade"] = "PE"
                    memory[name]["trade_symbol"] = pe
                    memory[name]["entry_price"] = pe_ltp
                    memory[name]["trade_high"] = pe_ltp
                    memory[name]["dynamic_sl"] = pe_ltp * 0.92
                    memory[name]["sl_hit_count"] = 0
                    if is_reentry:
                        memory[name]["reentry_count"] += 1
                        print("[SAME SIDE RE-ENTRY]", name, "PE", "| PRICE", pe_ltp)
                    memory[name]["last_exit_side"] = None
                    memory[name]["last_exit_reason"] = None
                    memory[name]["pe_entry_armed"] = False


        time.sleep(5)




# ===== START =====

token=login()

if token:

    print("BOT READY")

    try:
        scanner(token)

    except KeyboardInterrupt:
        print("\nBOT MANUALLY STOPPED")
        send("🛑 BOT MANUALLY STOPPED")
