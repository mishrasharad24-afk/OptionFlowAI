import requests
import time
import csv
from datetime import datetime, date


# ===== CONFIG =====

API_KEY = "tCEplvPZd+y8Ki7Dr5S7qtZr8QO3Tb+uQkgjKcGZdtc="

BOT_TOKEN = "7705146253:AAGpL1cyzqL6_afWFGdrXGAU5M0Ku1VCFVM"
CHAT_ID = "-1002519123618"

MASTER="./pytradingapi-typeA/mock_responses/instrument_scrip_master.csv"


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



# ===== LOGIN =====

def login():

    otp=input("Enter mStock TOTP: ")

    r=requests.post(
        "https://api.mstock.trade/openapi/typea/session/verifytotp",
        headers={
            "X-Mirae-Version":"1",
            "Content-Type":"application/x-www-form-urlencoded"
        },
        data={
            "api_key":API_KEY,
            "totp":otp
        }
    ).json()


    if r.get("status")=="success":

        print("LOGIN SUCCESS")

        send("✅ OPTION FIGHT BOT LOGIN")

        return r["data"]["access_token"]


    print("LOGIN FAILED")
    print(r)

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



                arr.append({
                    "symbol":sym,
                    "expiry":expd,
                    "strike":strike,
                    "side":side
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
# ===== OPTION FIGHT ENGINE =====

def scanner(token):

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
            "ce":0,
            "pe":0,
            "ce_avg":0,
            "pe_avg":0
        },

        "SENSEX":{
            "trade":None,
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



        if now >= "15:00":

            send("🛑 3 PM BOT CLOSED")

            break



        for name in ["NIFTY","SENSEX"]:


            spot_symbol = (
                "NSE:NIFTY 50"
                if name=="NIFTY"
                else
                "BSE:SENSEX"
            )


            spot=ltp(headers,spot_symbol)


            if not spot:
                continue



            


            ce,pe=find_atm(
                data[name],
                spot
            )


            if not ce or not pe:
                continue
            if not ce or not pe:
                continue



                continue

            ce_ltp=ltp(headers,ce)

            pe_ltp=ltp(headers,pe)


            if not ce_ltp or not pe_ltp:
                continue

            old_ce=memory[name]["ce"]
            old_pe=memory[name]["pe"]


            memory[name]["ce"]=ce_ltp
            memory[name]["pe"]=pe_ltp
            ce_score=0
            pe_score=0


            if old_ce==0:
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




            # ===== CE BUY =====

            if ce_score>=70 and memory[name]["trade"]!="CE":

                send(
                    f"🔥 {name} CE BUY\n"
                    f"{ce}\n"
                    f"PRICE {ce_ltp}"
                )

                memory[name]["trade"]="CE"




            # ===== PE BUY =====

            if pe_score>=70 and memory[name]["trade"]!="PE":

                send(
                    f"🔻 {name} PE BUY\n"
                    f"{pe}\n"
                    f"PRICE {pe_ltp}"
                )

                memory[name]["trade"]="PE"




            # ===== EXIT =====

            if memory[name]["trade"]=="CE" and pe_score>=50:

                send(
                    f"⚠️ EXIT {name} CE"
                )

                memory[name]["trade"]=None



            if memory[name]["trade"]=="PE" and ce_score>=50:

                send(
                    f"⚠️ EXIT {name} PE"
                )

                memory[name]["trade"]=None



        time.sleep(5)




# ===== START =====

token=login()

if token:

    print("BOT READY")

    scanner(token)
