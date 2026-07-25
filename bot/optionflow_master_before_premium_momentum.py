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
            "stable_direction":"NEUTRAL",
            "ce":0,
            "pe":0,
            "ce_avg":0,
            "pe_avg":0
        },

        "SENSEX":{
            "trade":None,
            "last_exit":0,
            "dir_candidate":"NEUTRAL",
            "dir_count":0,
            "stable_direction":"NEUTRAL",
            "ce":0,
            "pe":0,
            "ce_avg":0,
            "pe_avg":0
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

                    # ===== 3-CONFIRMATION STABLE AI DIRECTION =====
                    if ai_direction in ("BULLISH", "BEARISH"):

                        if memory[name]["dir_candidate"] == ai_direction:
                            memory[name]["dir_count"] += 1
                        else:
                            memory[name]["dir_candidate"] = ai_direction
                            memory[name]["dir_count"] = 1

                        if memory[name]["dir_count"] >= 3:
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

            ce_power=0
            pe_power=0

            for s in flow_ce:
                p=ltp(headers,s)
                if p and p > ce_ltp:
                    ce_power+=1

            for s in flow_pe:
                p=ltp(headers,s)
                if p and p > pe_ltp:
                    pe_power+=1

            if ce_power>=3:
                ce_score+=30

            if pe_power>=3:
                pe_score+=30
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
                "| CE_AVG", round(memory[name]["ce_avg"], 2),
                "| PE_AVG", round(memory[name]["pe_avg"], 2),
                "| CE_SCORE", ce_score,
                "| PE_SCORE", pe_score,
            )


            # ===== SAFE TRADE STATE / ANTI-FLIP LOGIC =====

            current_trade = memory[name]["trade"]

            # EXIT FIRST - require strong opposite flow
            if current_trade == "CE" and pe_score >= 80 and stable_direction == "BEARISH":
                print("[EXIT DEBUG]", name, "| TRADE CE | CE_SCORE", ce_score, "| PE_SCORE", pe_score, "| AI_DIR", ai_direction)
                send(
                    f"⚠️ EXIT {name} CE\n"
                    f"REASON: PE FLOW {pe_score} + STABLE AI {stable_direction}\n"
                    f"CE SCORE: {ce_score} | PE SCORE: {pe_score}\n"
                    f"COOLDOWN: 5 MIN"
                )
                memory[name]["trade"] = None
                memory[name]["last_exit"] = time.time()

            elif current_trade == "PE" and ce_score >= 80 and stable_direction == "BULLISH":
                print("[EXIT DEBUG]", name, "| TRADE PE | CE_SCORE", ce_score, "| PE_SCORE", pe_score, "| AI_DIR", ai_direction)
                send(
                    f"⚠️ EXIT {name} PE\n"
                    f"REASON: CE FLOW {ce_score} + STABLE AI {stable_direction}\n"
                    f"CE SCORE: {ce_score} | PE SCORE: {pe_score}\n"
                    f"COOLDOWN: 5 MIN"
                )
                memory[name]["trade"] = None
                memory[name]["last_exit"] = time.time()

            # ENTRY only if there was NO active trade at start of this cycle
            elif current_trade is None and (
                time.time() - memory[name].get("last_exit", 0) >= 300
            ):

                if ce_score >= 70 and stable_direction == "BULLISH":
                    send(
                        f"🔥 {name} CE BUY SIGNAL\n"
                        f"STRIKE: {int(round(spot / (50 if name == 'NIFTY' else 100)) * (50 if name == 'NIFTY' else 100))} CE\n"f"SYMBOL: {ce}\n"
                        f"PRICE: {ce_ltp}\n"
                        f"FLOW SCORE: {ce_score}\n"
                        f"AI DIR: {ai_direction}\n"f"STABLE DIR: {stable_direction}\n"
                        f"AI ACTION: {ai_action}\n"
                        f"AI SCORE: {ai_score:.2f}\n"
                        f"CONF: {ai_confidence}\n"
                        f"SETUP: {ai_setup}"
                    )
                    memory[name]["trade"] = "CE"

                elif pe_score >= 70 and stable_direction == "BEARISH":
                    send(
                        f"🔻 {name} PE BUY SIGNAL\n"
                        f"STRIKE: {int(round(spot / (50 if name == 'NIFTY' else 100)) * (50 if name == 'NIFTY' else 100))} PE\n"f"SYMBOL: {pe}\n"
                        f"PRICE: {pe_ltp}\n"
                        f"FLOW SCORE: {pe_score}\n"
                        f"AI DIR: {ai_direction}\n"f"STABLE DIR: {stable_direction}\n"
                        f"AI ACTION: {ai_action}\n"
                        f"AI SCORE: {ai_score:.2f}\n"
                        f"CONF: {ai_confidence}\n"
                        f"SETUP: {ai_setup}"
                    )
                    memory[name]["trade"] = "PE"


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
