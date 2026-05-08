import os, sys, json, logging, random, re, requests, threading, functools, html, time, atexit
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, request, jsonify, send_file, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from urllib.parse import quote

load_dotenv()
try:
    if sys.stdout.encoding != 'utf-8': sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8': sys.stderr.reconfigure(encoding='utf-8')
except Exception: pass

# ============================================================
# 🔑  CONFIG
# ============================================================
def get_config():
    try:
        p = str(Path(__file__).resolve().parent / "api_keys.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: pass
    return {}

CFG = get_config()

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN") or CFG.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID") or CFG.get("PHONE_NUMBER_ID", "")

def _digits_only(s):
    return "".join(filter(str.isdigit, str(s or "")))

ADMIN_PHONE     = "".join(filter(str.isdigit, str(os.environ.get("ADMIN_PHONE") or CFG.get("ADMIN_PHONE", "212778375026"))))
_default_catalog = "https://vip-boti.onrender.com"
CATALOG_URL     = (os.environ.get("CATALOG_URL") or CFG.get("CATALOG_URL") or _default_catalog).rstrip("/")
DASHBOARD_USER  = os.environ.get("DASHBOARD_USER") or CFG.get("DASHBOARD_USER", "admin")
DASHBOARD_PASS  = os.environ.get("DASHBOARD_PASS") or CFG.get("DASHBOARD_PASS", "vip2026")
API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# ============================================================
# 📋  LOGGING
# ============================================================
BASE_DIR = str(Path(__file__).resolve().parent)
_log_path = os.path.join(BASE_DIR, "log.txt")
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
_rh = RotatingFileHandler(_log_path, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
_rh.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[_sh, _rh])

if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
    logging.warning("⚠️ [CONFIG] ACCESS_TOKEN or PHONE_NUMBER_ID missing — outbound WhatsApp will fail until set in environment or api_keys.json (local).")

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# ============================================================
# 📂  DATA HELPERS
# ============================================================
CATALOG_FILE  = os.path.join(BASE_DIR, "catalog.json")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
ORDERS_FILE   = os.path.join(BASE_DIR, "orders.json")
LEADS_FILE    = os.path.join(BASE_DIR, "known_leads.json")
RESPONSES_FILE = os.path.join(BASE_DIR, "responses.json")

shared_lock = threading.RLock()
# Use OrderedDict for processed_messages to avoid unbounded growth (LRU cache)
processed_messages = OrderedDict()
MAX_PROCESSED_MESSAGES = 1000  # Keep only last 1000 message IDs in memory

# Thread pool for WhatsApp sending (prevents thread explosion)
whatsapp_executor = ThreadPoolExecutor(max_workers=15)

def with_lock(f):
    """Decorator to ensure thread-safety for state-modifying functions."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        with shared_lock:
            return f(*args, **kwargs)
    return wrapper

@with_lock
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

@with_lock
def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def _touch_session(sess):
    """Unix timestamp for session TTL cleanup (keep_alive)."""
    sess["timestamp"] = time.time()

# ============================================================
# 💬  RESPONSES ENGINE (no AI — 100% stable)
# ============================================================
_RESPONSES_CACHE = None
def get_responses():
    global _RESPONSES_CACHE
    if _RESPONSES_CACHE is None:
        _RESPONSES_CACHE = load_json(RESPONSES_FILE, {})
    return _RESPONSES_CACHE

def pick_response(intent, **kwargs):
    """Pick a random response for the given intent and fill in placeholders."""
    responses = get_responses()
    templates = responses.get(intent, responses.get("unknown", ["مرحبا! صيفط *أرقامكم* 👑"]))
    if isinstance(templates, str):
        templates = [templates]
    kwargs.setdefault("catalog_url", CATALOG_URL)
    text = random.choice(templates)
    try:
        text = text.format(**kwargs)
    except KeyError:
        pass
    return text

# ============================================================
# 📦  CATALOG HELPERS
# ============================================================
def get_all_numbers():
    catalog = load_json(CATALOG_FILE, {})
    nums = []
    for tier, items in catalog.items():
        for item in items:
            item["tier"] = tier
            nums.append(item)
    return nums

# Regex to extract Moroccan phone numbers from messy user input
_MOROCCAN_PHONE_RE = re.compile(
    r'(?:(?:\+?212|00212)[\s.-]?)?'   # optional country code: +212, 212, 00212
    r'(0[5-7])'                         # mandatory: leading 05/06/07
    r'[\s./-]?'                         # optional separator
    r'(\d{1,2})[\s./-]?(\d{1,2})'     # next digit groups
    r'[\s./-]?(\d{1,2})[\s./-]?(\d{1,2})' # remaining groups
)

def _extract_moroccan_numbers(text):
    """Extract all plausible Moroccan mobile numbers from text, return as 10-digit strings."""
    candidates = []
    for m in _MOROCCAN_PHONE_RE.finditer(text):
        raw = ''.join(m.groups())
        digits = ''.join(filter(str.isdigit, raw))
        if len(digits) == 10 and digits[0] == '0':
            candidates.append(digits)
    # Fallback: brute-force strip all digits if regex found nothing
    if not candidates:
        all_digits = ''.join(filter(str.isdigit, text))
        # Strip leading 212 or 00212
        for prefix in ('00212', '212'):
            if all_digits.startswith(prefix):
                all_digits = '0' + all_digits[len(prefix):]
                break
        if len(all_digits) >= 10 and all_digits[0] == '0':
            candidates.append(all_digits[:10])
    return candidates

def find_number_in_catalog(text):
    """
    Find a VIP number in catalog from user text.
    Uses robust Moroccan phone regex to handle spaces, dashes, country codes.
    Returns: (item, tier) or (None, None)
    """
    catalog = load_json(CATALOG_FILE, {})
    candidates = _extract_moroccan_numbers(text)
    if not candidates:
        return None, None
    
    for candidate in candidates:
        for tier, items in catalog.items():
            for item in items:
                if item.get("status", "available") != "available":
                    continue
                item_digits = "".join(filter(str.isdigit, item["number"]))
                # Match: full 10-digit, or last 9 digits
                if candidate == item_digits or candidate[1:] == item_digits[1:]:
                    return item, tier
    
    return None, None

def is_direct_number_query(text):
    """
    Detect if user is directly asking about or mentioning a specific number.
    Returns True if text contains Arabic/French/English number query keywords.
    """
    t = text.lower()
    # Keywords indicating direct number inquiry: "رقم", "عندك", "كاين", "donne", "envoie", "nomero"
    direct_keywords = [
        "رقم", "عندك", "كاين", "ديالكم", "ديالنا",
        "donne", "envoie", "nomero", "numero", "give", "send", "have"
    ]
    return any(kw in t for kw in direct_keywords)

def format_catalog_message():
    catalog = load_json(CATALOG_FILE, {})
    
    # Safety check for empty or invalid catalog
    if not catalog or not isinstance(catalog, dict):
        return "⚠️ الكتالوج فارغ دابا — أضف نوامر دابا باش تشوفهم هنا! 📋"
    
    lines = ["🌟 *أرقام VIP المتوفرة حالياً:* \n"]
    has_available = False
    
    for tier, items in catalog.items():
        if not isinstance(items, list): continue
        available = [i for i in items if isinstance(i, dict) and i.get("status", "available") == "available"]
        if not available: continue
        has_available = True
        lines.append(f"🔹 *{tier.upper()}:*")
        for item in available:
            lines.append(f"   📱 {item['number']} — *{item.get('price', 'N/A')}*")
        lines.append("")
    
    # إذا ما كاينش نوامر متوفرين
    if not has_available:
        return "😕 ما كاينش نوامر متوفرين دابا — خاصك تتصل بينا مباشرة! 📞"
    
    lines.append(f"🌐 شوف الكتالوج كامل هنا: {CATALOG_URL}")
    lines.append("\nصيفط ليا الرقم اللي عجبك باش نكملو! 🚀")
    return "\n".join(lines)

@with_lock
def mark_number_sold(number_str):
    catalog = load_json(CATALOG_FILE, {})
    clean_target = "".join(filter(str.isdigit, str(number_str)))
    if len(clean_target) < 9: return False
    found = False
    for tier, items in catalog.items():
        for item in items:
            clean_item = "".join(filter(str.isdigit, item["number"]))
            if clean_item == clean_target or clean_item.endswith(clean_target[-9:]):
                item["status"] = "sold"
                found = True
    if found: save_json(CATALOG_FILE, catalog)
    return found

def _is_allowed_price(price_text):
    digits = "".join(filter(str.isdigit, str(price_text)))
    if not digits:
        return False
    value = int(digits)
    return 100 <= value <= 200

# ============================================================
# 🧠  INTENT DETECTION
# ============================================================
GREETING_KW = ["سلام","السلام","مرحبا","أهلا","hi","hello","bonjour","سلا","اهلا","ahlan","mrhba","hola","salam","slm","cv","labas","bsh","yo","salut","hey"]
CATALOG_KW  = ["الكتالوج","أرقام","ارقام","كتالوج","liste","ليستة","عرض","نوامر","nwamer","catalog","كلهم","catalogue","ارقامكم","arqam","bghit nwamer","warini", "les numéros", "les numeros", "numbers", "numéro", "numero", "نماري", "نمرة", "النوامر", "بغينا النوامر", "ورينا النوامر", "أريد أرقام", "nmari", "nwamar", "واش كاين", "الجديد", "inwi", "orange", "iam"]
PRICE_KW    = ["الثمن","ثمن","بشحال","بشحال هادي","prix","price","كم","غالي","رخيص","سعر","combien","bch7al","thaman","ch7al","شحال","عرض","inwi","orange","iam"]
HELP_KW     = ["مساعدة","help","aide","كيفاش","comment","شنو","wayfash","كيف","chno","wach","how"]
CANCEL_KW   = ["لا","cancel","إلغاء","!reset","/reset","stop","خلاص","مابغيتش","annuler"]
THANKS_KW   = ["شكرا","merci","thanks","thank","بارك","choukran","mrc","jazak"]
NEGOT_KW    = ["غالي","رخص","naqes","discount","تخفيض","بزاف","cher","expensive","rkhis"]
DELIVERY_KW = ["توصيل","livraison","delivery","كيوصل","فين يوصل","kifach","tawsil"]
TRUST_KW    = ["ثقة","واش حقيقي","serious","arnaque","مضمون","sérieux","legit","wa9i3i","bsa7"]

# ============================================================
# 🎯  CONTACT REQUEST KEYWORDS (Historical Keywords)
# ============================================================
# الأفعال والجذور المتعلقة بطلب المعلومات
CONTACT_VERBS = [
    "3tini", "3etini", "sift", "sayft", "bghit", "brit", "momkin", "passi", "donne", "khasni", "khassni",
    "ارسل", "أعطني", "اعطني", "عطيني", "اعطيني", "صيفط", "سيفط", "بغيت", "ممكن", "خاصني", "خصني", "دابا"
]

# الأسماء والكلمات المتعلقة برقم والتواصل
CONTACT_NOUNS = [
    "nmra", "nemra", "nmera", "namra", "num", "numero", "ra9m", "r9m", "tel", "tilifon", "telfon", "wtsp", "whatsapp", "watsap",
    "نمرة", "النمرة", "نميرة", "رقم", "الرقم", "تيليفون", "تليفون", "هاتف", "واتساب", "وتساب", "التواصل", "الاتصال"
]

def detect_intent(text):
    t = text.lower().strip()
    words = set(re.split(r'\s+', t))
    
    # --- PRIORITY 1: DIRECT NUMBER QUERY (Increased Priority) ---
    digits = "".join(filter(str.isdigit, t))
    if len(digits) >= 9 and is_direct_number_query(t):
        return "number_inquiry"
    
    # --- PRIORITY 2: CATALOG (prevents greeting override) ---
    for kw in CATALOG_KW:
        if kw in t: return "show_catalog"
    
    # --- PRIORITY 3: CHECK FOR CONTACT REQUEST ---
    has_verb = any(v in t for v in CONTACT_VERBS)
    has_noun = any(n in t for n in CONTACT_NOUNS)
    is_short_msg = len(t.split()) <= 3 and has_noun
    
    if (has_verb and has_noun) or is_short_msg:
        return "contact_request"
    
    # --- PRIORITY 4: GREETING (after catalog) ---
    for kw in GREETING_KW:
        if kw in t: return "greeting"
    
    # --- PRIORITY 5: CANCEL: exact-word match for short words like "لا" ---
    for kw in CANCEL_KW:
        if len(kw) <= 2:
            if kw in words: return "cancel"
        else:
            if kw in t: return "cancel"
    
    # --- PRIORITY 6: OTHER INTENTS ---
    for kw in THANKS_KW:
        if kw in t: return "thanks"
    for kw in PRICE_KW:
        if kw in t: return "price_inquiry"
    for kw in NEGOT_KW:
        if kw in t: return "negotiation"
    for kw in DELIVERY_KW:
        if kw in t: return "delivery_question"
    for kw in TRUST_KW:
        if kw in t: return "trust_question"
    for kw in HELP_KW:
        if kw in t: return "help"

    return "unknown"

# ============================================================
def send_whatsapp(to, text):
    """Send WhatsApp message with timeout and error handling"""
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logging.error(f"❌ [SEND BLOCKED] Missing ACCESS_TOKEN or PHONE_NUMBER_ID")
        return False
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:4096]}}
    try:
        logging.info(f"📤 [ATTEMPT] Sending to {to}...")
        r = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        logging.info(f"📲 [SEND] To: {to} | Status: {r.status_code}")
        if r.status_code not in (200, 201):
            logging.error(f"❌ [SEND FAIL] Status: {r.status_code} | META API ERROR: {r.text}")
        return r.status_code in (200, 201)
    except requests.Timeout:
        logging.error(f"⏱️ [SEND TIMEOUT] To: {to}")
        return False
    except Exception as e:
        logging.error(f"❌ [SEND ERROR] To: {to} | Error: {e}")
        return False

def send_whatsapp_async(to, text):
    """Send WhatsApp message asynchronously using thread pool"""
    return whatsapp_executor.submit(send_whatsapp, to, text)

def send_admin_notification(phone, msg):
    """Send an urgent admin notification safely."""
    try:
        send_whatsapp_async(ADMIN_PHONE, msg)
        print(f"[SYSTEM] Notification sent to {ADMIN_PHONE}")
        logging.info(f"✅ [ADMIN NOTIFICATION DISPATCHED] {ADMIN_PHONE}")
    except Exception as e:
        logging.error(f"❌ [ADMIN NOTIFICATION FAIL] {ADMIN_PHONE} | Error: {e}")
    return None

def notify_admin_media(sender, media_type):
    if sender == ADMIN_PHONE:
        return
    media_label = "صورة/ملف" if media_type in ("image", "document", "audio", "video", "sticker") else "ميديا"
    alert = (
        "⚠️ Media received from user\n"
        f"From: {sender}\n"
        f"Type: {media_type} ({media_label})\n"
        f"Link: https://wa.me/{sender}"
    )
    try:
        send_whatsapp_async(ADMIN_PHONE, alert)
        logging.info(f"✅ [MEDIA ALERT SENT] To: {ADMIN_PHONE} | From: {sender} | Type: {media_type}")
    except Exception as e:
        logging.error(f"❌ [MEDIA ALERT FAIL] To: {ADMIN_PHONE} | From: {sender} | Error: {e}")

# ============================================================
# 🛠️  ADMIN COMMANDS
# ============================================================
def handle_admin_command(sender, text):
    parts = text.strip().lower().split()
    if not parts: return "Admin mode."
    base = parts[0]

    def get_digits(t):
        return re.findall(r'\d{7,15}', "".join(filter(lambda x: x.isdigit() or x.isspace(), t)))

    if base == "!help":
        return ("🛠️ *أوامر التحكم:*\n\n"
                "• `!stats` - إحصائيات\n• `!sold [رقم]` - تعليم كمباع\n"
                "• `!add [رقم] [صنف] [ثمن]` - إضافة\n• `!delete [رقم]` - حذف\n"
                "• `!reset` - مسح الجلسات\n• `!test` - اختبار الإشعارات")
    if base == "!stats":
        nums = get_all_numbers()
        avail = len([n for n in nums if n.get("status") == "available"])
        sold = len([n for n in nums if n.get("status") == "sold"])
        orders = load_json(ORDERS_FILE, [])
        return f"📊 *إحصائيات:*\n✅ متوفر: {avail}\n❌ مباع: {sold}\n📋 طلبات: {len(orders)}"
    if base == "!sold":
        targets = get_digits(text)
        if not targets: return "❌ صيفط الرقم."
        c = sum(1 for t in targets if mark_number_sold(t))
        return f"✅ تم تعليم {c} أرقام كمباعة." if c else "❌ ما لقيناش الرقم."
    if base in ("!delete", "!del"):
        targets = get_digits(text)
        if not targets: return "❌ صيفط الرقم."
        catalog = load_json(CATALOG_FILE, {})
        deleted = []
        for t in targets:
            for tier in catalog:
                before = len(catalog[tier])
                catalog[tier] = [i for i in catalog[tier] if "".join(filter(str.isdigit, i["number"])) != t and not "".join(filter(str.isdigit, i["number"])).endswith(t[-9:])]
                if len(catalog[tier]) < before: deleted.append(t)
        if deleted:
            save_json(CATALOG_FILE, catalog)
            return "🗑️ تم الحذف:\n" + "\n".join(f"• {n}" for n in set(deleted))
        return "❌ ما لقيناش."
    if base == "!add" and len(parts) > 3:
        num, tier, price = parts[1], parts[2], " ".join(parts[3:])
        if not _is_allowed_price(price):
            return "❌ الثمن المسموح فقط بين 100 و 200 DH."
        catalog = load_json(CATALOG_FILE, {})
        if tier not in catalog: catalog[tier] = []
        catalog[tier].append({"number": num, "price": price, "status": "available", "tier": tier})
        save_json(CATALOG_FILE, catalog)
        return f"✅ تم إضافة {num} إلى {tier}."
    if base == "!reset":
        save_json(SESSIONS_FILE, {})
        return "♻️ تم تصفير الجلسات."
    if base == "!test":
        try:
            send_whatsapp_async(ADMIN_PHONE, "🔔 Test - Notifications Working! ✅")
            return f"✅ Test notification sent to {ADMIN_PHONE}."
        except Exception as e:
            logging.error(f"❌ [TEST NOTIFY FAIL] {e}")
            return f"❌ Test failed: {e}"
    return "🛠️ أمر غير معروف. صيفط `!help`"

# ============================================================
# 🧠  MAIN LOGIC — 100% responses.json, ZERO AI
# ============================================================
def _get_known_leads():
    leads = load_json(LEADS_FILE, {})
    if isinstance(leads, list):
        leads = {str(k): {"name": ""} for k in leads}
        save_json(LEADS_FILE, leads)
    return leads

@with_lock
def _save_known_lead(sender, name=""):
    leads = _get_known_leads()
    if sender not in leads: leads[sender] = {"name": name}
    elif name: leads[sender]["name"] = name
    save_json(LEADS_FILE, leads)

@with_lock
def handle_logic(sender, text):
    sessions = load_json(SESSIONS_FILE, {})
    raw_text = text.strip()

    # ADMIN COMMANDS — Execute properly
    if sender == ADMIN_PHONE:
        if raw_text.startswith("!"): return handle_admin_command(sender, raw_text)
        return None

    leads = _get_known_leads()
    is_new_lead = sender not in leads

    # --- ADMIN ALERT FOR NEW LEAD ---
    if is_new_lead and sender != ADMIN_PHONE:
        _save_known_lead(sender)
        interest = "👀 استفسار عام"
        vip_item, _ = find_number_in_catalog(raw_text)
        if vip_item: interest = f"🎯 مهتم بـ: *{vip_item['number']}*"
        
        alert = pick_response("admin_new_lead", sender=sender, message=raw_text[:100], interest=interest, time=datetime.now().strftime('%H:%M:%S'))
        send_whatsapp_async(ADMIN_PHONE, alert)
        logging.info(f"🔔 [ADMIN ALERT] New Lead {sender} notified to {ADMIN_PHONE}")

    # GATEKEEPER: prevent name loop
    if not is_new_lead and leads[sender].get("name"):
        if sender in sessions and sessions[sender].get("step") == "initial_name":
            sessions.pop(sender, None)
            save_json(SESSIONS_FILE, sessions)

    # NEW LEAD FLOW
    if is_new_lead:
        _save_known_lead(sender)
        vip_item, _ = find_number_in_catalog(raw_text)
        sessions[sender] = {"step": "initial_name", "first_msg": raw_text}
        if vip_item: sessions[sender]["vip_item"] = vip_item
        _touch_session(sessions[sender])
        save_json(SESSIONS_FILE, sessions)
        return pick_response("ask_name_with_number", number=vip_item["number"]) if vip_item else pick_response("ask_name_initial")

    # IMMEDIATE NUMBER VERIFICATION
    t_low = raw_text.lower()
    if is_direct_number_query(t_low) and len("".join(filter(str.isdigit, t_low))) >= 9:
        vip_item, _ = find_number_in_catalog(raw_text)
        if vip_item: return pick_response("number_available", number=vip_item["number"], price=vip_item.get("price", "N/A"))
        else: return pick_response("number_not_found", catalog_url=CATALOG_URL)

    # SESSION HANDLING
    if sender in sessions and "step" in sessions[sender]:
        session = sessions[sender]
        step = session["step"]

        if step == "initial_name":
            name = raw_text
            # 1. Save name permanently in leads
            _save_known_lead(sender, name)
            print(f"[SYSTEM] Name '{name}' saved for {sender}")
            vip_item = session.get("vip_item")
            if vip_item:
                session["step"] = "address"
                session["data"] = {"name": name}
                _touch_session(session)
                sessions[sender] = session
                save_json(SESSIONS_FILE, sessions)
                return pick_response("welcome_and_ask_city", name=name)
            else:
                # Clear session so they don't loop, jump straight to catalog
                sessions.pop(sender, None)
                save_json(SESSIONS_FILE, sessions)
                catalog_text = format_catalog_message()
                return pick_response("show_catalog", catalog=catalog_text)

        if step == "address":
            city = raw_text
            vip_item = session.get("vip_item")
            if not vip_item:
                sessions.pop(sender, None)
                save_json(SESSIONS_FILE, sessions)
                return pick_response("unknown")
            name = leads.get(sender, {}).get("name", "?")
            vip_num = vip_item["number"]
            orders = load_json(ORDERS_FILE, [])
            order_id = f"ORD-{datetime.now().strftime('%d%m%Y-%H%M%S')}"
            orders.append({
                "id": order_id, "sender": sender, "vip_number": vip_num,
                "price": vip_item.get("price", "N/A"),
                "customer": {"name": name, "address": city, "phone": "whatsapp"},
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "pending"
            })
            save_json(ORDERS_FILE, orders)
            mark_number_sold(vip_num)
            admin_msg = pick_response("admin_order", number=vip_num, name=name, city=city, phone="واتساب", sender=sender)
            send_whatsapp_async(ADMIN_PHONE, admin_msg)
            sessions.pop(sender, None)
            save_json(SESSIONS_FILE, sessions)
            return pick_response("order_complete", number=vip_num, name=name, city=city)

    # INTENT DETECTION
    intent = detect_intent(raw_text)
    if intent == "show_catalog": return pick_response("show_catalog", catalog=format_catalog_message())
    if intent == "number_inquiry": return pick_response("number_not_found")
    if intent == "contact_request": return pick_response("contact_request", catalog_url=CATALOG_URL)
    if intent == "cancel" and sender in sessions:
        sessions.pop(sender, None)
        save_json(SESSIONS_FILE, sessions)
    return pick_response(intent)

# ============================================================
# 🌐  ROUTES
# ============================================================
@app.route("/", methods=["GET"])
def home():
    try: return send_from_directory('dist', 'index.html')
    except: return "<h2>✅ VIP Numbers Bot — React App Running</h2>", 200

@app.route("/health")
def health():
    avail = len([n for n in get_all_numbers() if n.get('status','available') == 'available'])
    config_status = "✅" if (ACCESS_TOKEN and PHONE_NUMBER_ID) else "❌"
    return jsonify({
        "status": "ok", 
        "bot": "VIP Numbers Bot", 
        "ai": "disabled (responses.json)", 
        "numbers_available": avail, 
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": config_status,
        "access_token_set": bool(ACCESS_TOKEN),
        "phone_number_id": PHONE_NUMBER_ID,
        "webhook_url": f"{CATALOG_URL}/webhook"
    }), 200

def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != DASHBOARD_USER or auth.password != DASHBOARD_PASS:
            return Response("🔒 Access Denied.", 401, {"WWW-Authenticate": 'Basic realm="VIP Admin"'})
        return f(*args, **kwargs)
    return decorated

@app.route("/logs", methods=["GET"])
@require_auth
def view_logs():
    """View recent bot logs (admin only)"""
    try:
        lines = request.args.get("lines", 50, type=int)
        if os.path.exists(_log_path):
            with open(_log_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if lines else all_lines
                return f"<pre>{html.escape(''.join(recent))}</pre>", 200
        return "<p>No logs found</p>", 200
    except Exception as e:
        return f"<p>Error: {e}</p>", 500

@app.route("/test", methods=["POST"])
def test_webhook():
    """Test endpoint - simulate WhatsApp message for debugging"""
    try:
        data = request.get_json(force=True)
        test_phone = data.get("phone", "212638388885").replace("+", "")
        test_message = data.get("message", "سلام").strip()
        
        logging.info(f"🧪 [TEST] Simulating message from {test_phone}: {test_message}")
        
        # Simulate webhook message
        reply = handle_logic(test_phone, test_message) or ""
        
        # Actually send it via WhatsApp
        send_status = send_whatsapp(test_phone, reply) if reply else False
        
        return jsonify({
            "ok": True,
            "message_sent": send_status,
            "reply": reply,
            "test_phone": test_phone
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """WhatsApp Cloud API Webhook"""
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                logging.info("✅ [WEBHOOK] Verification successful!")
                return challenge, 200
            else:
                logging.warning(f"❌ [WEBHOOK] Invalid token!")
                return "Forbidden", 403
        return "Webhook is active", 200
    
    try:
        data = request.get_json(force=True)
        logging.info(f"📥 [WEBHOOK RAW] {str(data)[:300]}...")
        
        if 'entry' in data and data['entry'][0]['changes'][0]['value'].get('messages'):
            msg = data['entry'][0]['changes'][0]['value']['messages'][0]
            msg_id = msg.get('id', '')
            
            # Check if already processed (LRU cache)
            if msg_id in processed_messages:
                logging.info(f"⏭️  [WEBHOOK] Already processed: {msg_id}")
                return "ok", 200
            
            # Add to processed messages
            with shared_lock:
                processed_messages[msg_id] = True
                # Keep only last MAX_PROCESSED_MESSAGES
                if len(processed_messages) > MAX_PROCESSED_MESSAGES:
                    # Remove oldest entries
                    for _ in range(len(processed_messages) - MAX_PROCESSED_MESSAGES):
                        processed_messages.popitem(last=False)
            
            sender = "".join(filter(str.isdigit, msg['from']))
            
            # --- WEBHOOK FIRST ALERT (FIRE & FORGET) ---
            if sender != ADMIN_PHONE:
                if msg.get('type') == 'text':
                    body_preview = msg['text']['body'][:100]
                    alert_msg = f"🚨 رسالة جديدة من: {sender}\nالرسالة: {body_preview}\nتواصل: https://wa.me/{sender}"
                    send_whatsapp_async(ADMIN_PHONE, alert_msg)
                    print(f"[SYSTEM] Urgent Lead Alert sent to {ADMIN_PHONE} for {sender}")
                else:
                    alert_msg = f"🚨 ميديا جديدة من: {sender}\nالنوع: {msg.get('type')}\nتواصل: https://wa.me/{sender}"
                    send_whatsapp_async(ADMIN_PHONE, alert_msg)

            with shared_lock:
                if msg_id in processed_messages: return "ok", 200
                processed_messages[msg_id] = True
                if len(processed_messages) > MAX_PROCESSED_MESSAGES: processed_messages.popitem(last=False)
            
            if msg.get('type') == 'text':
                reply = handle_logic(sender, msg['text']['body'])
                if reply: send_whatsapp_async(sender, reply)
            elif msg.get('type') in ('image','document','audio','video','sticker'):
                reply = pick_response("media_received")
                if reply: send_whatsapp_async(sender, reply)
                    
        return "ok", 200
    except Exception as e:
        logging.error(f"❌ [WEBHOOK ERROR]: {e}")
        # Always return 200 to Meta to prevent retry loops on processing errors
        return "ok", 200

@app.route("/api/register", methods=["POST"])
@with_lock
def api_register():
    """Register a phone number to receive bot notifications and updates"""
    try:
        data = request.get_json(force=True)
        phone = "".join(filter(str.isdigit, str(data.get("phone", "")).strip()))
        name = data.get("name", "").strip()
        
        if not phone or len(phone) < 9:
            return jsonify({"error": "رقم هاتف غير صحيح — صيفط رقم صحيح 📱"}), 400
        
        # Save to known leads
        leads = _get_known_leads()
        leads[phone] = {"name": name}
        save_json(LEADS_FILE, leads)
        
        # Log registration
        logging.info(f"✅ [REGISTER] Phone: {phone} | Name: {name}")
        
        # Send welcome message
        msg = f"✨ مرحبا {name or 'سيدي'}! \n\n✅ تم تسجيلك بنجاح!\n\nستتلقى من الآن الجديد من الأرقام المتاحة والعروضات. 🎯\n\nصيفط ليا الرقم اللي بغيت باش نكملو 📞"
        send_whatsapp_async(phone, msg)
        
        return jsonify({"ok": True, "message": "✅ تم التسجيل بنجاح!", "phone": phone}), 200
    except Exception as e:
        logging.error(f"[Register Error]: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        data = request.get_json(force=True)
        user_text = data.get("prompt", "").strip()
        sender = data.get("sender", "web_user_default")
        if not user_text: return jsonify({"response": "صيفط ليا رسالتك 😊"})
        reply = handle_logic(sender, user_text)
        return jsonify({"response": reply or ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# 👁️  PAGE VISIT TRACKER — Notify admin on every new visitor
# ============================================================
_visit_throttle = {}  # ip -> last_notify_timestamp
VISIT_THROTTLE_SECS = 300  # 5 minutes per IP to avoid spam

@app.route("/api/page-visit", methods=["POST"])
def api_page_visit():
    try:
        data = request.get_json(force=True) or {}
        ip_address = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
        # Take first IP if comma-separated (proxy chain)
        ip_clean = ip_address.split(",")[0].strip() if ip_address else "unknown"
        user_agent = request.headers.get("User-Agent", "N/A")
        referrer   = data.get("referrer", request.referrer or "direct")
        page       = data.get("page", "/")
        timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Throttle: only notify once per IP per VISIT_THROTTLE_SECS
        now = time.time()
        last = _visit_throttle.get(ip_clean, 0)
        if now - last < VISIT_THROTTLE_SECS:
            return jsonify({"ok": True, "throttled": True}), 200

        _visit_throttle[ip_clean] = now
        # Prune old entries to keep dict small
        if len(_visit_throttle) > 500:
            cutoff = now - VISIT_THROTTLE_SECS
            for k in [k for k, v in _visit_throttle.items() if v < cutoff]:
                _visit_throttle.pop(k, None)

        alert = (
            f"👁️ *زيارة جديدة للموقع!*\n"
            f"🌐 IP: {ip_clean}\n"
            f"📄 الصفحة: {page}\n"
            f"🔗 المصدر: {referrer}\n"
            f"📱 الجهاز: {user_agent[:80]}\n"
            f"⏰ الوقت: {timestamp}"
        )

        logging.info(f"👁️ [PAGE VISIT] IP: {ip_clean} | Page: {page}")
        try:
            future = send_whatsapp_async(ADMIN_PHONE, alert)
            # Log if there's an error
            def _log_result(f):
                try:
                    result = f.result()
                    logging.info(f"✅ [PAGE VISIT NOTIFICATION] Sent to {ADMIN_PHONE}: {result}")
                except Exception as e:
                    logging.error(f"❌ [PAGE VISIT NOTIFICATION FAILED] {e}")
            future.add_done_callback(_log_result)
        except Exception as e:
            logging.error(f"❌ [PAGE VISIT] Failed to send notification: {e}")

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.error(f"❌ [PAGE VISIT ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/whatsapp-click", methods=["POST"])
def api_whatsapp_click():
    try:
        data = request.get_json(force=True)
        number = data.get("number", "").strip()
        price = data.get("price", "N/A").strip()
        tier = data.get("tier", "VIP").strip()
        sender_info = data.get("sender", "")
        user_agent = request.headers.get("User-Agent", "")
        ip_address = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)

        if not number:
            return jsonify({"error": "number required"}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        admin_alert = (
            f"🔥 *كليك على رقم VIP من الويب!*\n"
            f"📱 الرقم: *{number}*\n"
            f"💰 السعر: *{price}*\n"
            f"🎯 المستوى: *{tier}*\n"
            f"👤 المعلومات: {sender_info or 'N/A'}\n"
            f"🌐 IP: {ip_address}\n"
            f"⏰ الوقت: {timestamp}\n"
            f"📊 الجهاز: {user_agent[:60]}\n\n"
            f"👉 اضغط للتواصل: https://wa.me/{ADMIN_PHONE}"
        )

        # Send notification asynchronously to admin
        try:
            send_whatsapp_async(ADMIN_PHONE, admin_alert)
        except Exception as notify_err:
            logging.error(f"❌ [ADMIN NOTIFY FAIL] Could not send notification: {notify_err}")
        
        logging.info(f"✅ [WHATSAPP CLICK] Number: {number} | Tier: {tier} | Price: {price} | IP: {ip_address} | Notification sent to {ADMIN_PHONE}")

        return jsonify({"ok": True, "redirect": f"https://wa.me/{ADMIN_PHONE}?text={quote(f'Salam, bghit nreservi had nmra VIP: {number} - {price} - Tier: {tier}')}"})
    except Exception as e:
        logging.error(f"❌ [WHATSAPP CLICK ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/static/<path:filename>")
def serve_static(filename): return send_file(os.path.join(BASE_DIR, filename))

@app.route("/api/full_catalog")
def api_catalog(): return jsonify(load_json(CATALOG_FILE, {}))

@app.route("/api/orders")
@require_auth
def api_orders(): return jsonify(load_json(ORDERS_FILE, []))

@app.route("/api/sessions")
def api_sessions(): return jsonify(load_json(SESSIONS_FILE, {}))

@app.route("/api/catalog_stats")
def api_catalog_stats():
    catalog = load_json(CATALOG_FILE, {})
    avail = sum(1 for items in catalog.values() for i in items if i.get("status","available") == "available")
    sold = sum(1 for items in catalog.values() for i in items if i.get("status") == "sold")
    return jsonify({"total": avail+sold, "available": avail, "sold": sold})

@app.route("/api/catalog/manage", methods=["POST"])
@require_auth
@with_lock
def api_catalog_manage():
    try:
        data = request.get_json(force=True)
        action = data.get("action")
        catalog = load_json(CATALOG_FILE, {})
        if action == "add":
            num = data.get("number","").strip()
            tier = data.get("tier","gold").strip().lower()
            price = data.get("price","100 DH").strip()
            if not num: return jsonify({"error": "number required"}), 400
            if not _is_allowed_price(price):
                return jsonify({"error": "price must be between 100 and 200 DH"}), 400
            if tier not in catalog: catalog[tier] = []
            catalog[tier].append({"number": num, "price": price, "status": "available"})
            save_json(CATALOG_FILE, catalog)
            return jsonify({"ok": True})
        elif action == "delete":
            num = data.get("number","").strip()
            for t in catalog:
                catalog[t] = [i for i in catalog[t] if i.get("number") != num]
            save_json(CATALOG_FILE, catalog)
            return jsonify({"ok": True})
        return jsonify({"error": "unknown action"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/broadcast", methods=["POST"])
@require_auth
def api_broadcast():
    """Send a message to all registered users (admin only)"""
    try:
        data = request.get_json(force=True)
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"error": "رسالة مطلوبة"}), 400
        
        leads = _get_known_leads()
        sent_count = 0
        failed = []
        
        for phone in leads:
            if phone != ADMIN_PHONE:  # Don't send to admin twice
                if send_whatsapp(phone, message):
                    sent_count += 1
                else:
                    failed.append(phone)
        
        logging.info(f"📢 [BROADCAST] Sent: {sent_count} | Failed: {len(failed)}")
        return jsonify({
            "ok": True, 
            "sent": sent_count, 
            "failed": len(failed),
            "message": f"تم الإرسال إلى {sent_count} مستخدم ✅"
        }), 200
    except Exception as e:
        logging.error(f"[Broadcast Error]: {e}")
        return jsonify({"error": str(e)}), 500

# --- End of Routes ---

@app.route("/whatsapp/<phone>", methods=["GET"])
def whatsapp_redirect(phone):
    """Direct WhatsApp link endpoint - format: /whatsapp/0638388885 or /whatsapp/212638388885"""
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) < 9:
        return jsonify({"error": "Invalid phone number"}), 400
    # Ensure it starts with country code
    if not clean_phone.startswith("212"):
        clean_phone = "212" + clean_phone.lstrip("0") if clean_phone.startswith("0") else "212" + clean_phone
    
    wa_url = f"https://wa.me/{clean_phone}"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connecting to WhatsApp...</title>
        <script>window.location.href='{wa_url}';</script>
    </head>
    <body>Redirecting...</body>
    </html>
    """

@app.route("/<path:path>")
def catch_all(path):
    """Serve React app for all routes that don't match API or static files"""
    if (path.startswith('api/') or path.startswith('webhook') or path.startswith('dashboard') 
        or path.startswith('static/') or path.startswith('pastry') or path.startswith('whatsapp')):
        return jsonify({"error": "Not found"}), 404
    try:
        return send_from_directory('dist', 'index.html')
    except:
        return "<h2>✅ VIP Numbers Bot — React App Running</h2>", 200

# --- Keep-alive & Maintenance ---
def keep_alive():
    """Periodically ping the server and clean up memory"""
    url = os.environ.get("RENDER_EXTERNAL_URL", "")
    counter = 0
    while True:
        try:
            time.sleep(300)  # Ping every 5 minutes
            
            # Ping the server
            if url:
                try:
                    r = requests.get(f"{url}/health", timeout=10)
                    if r.status_code == 200:
                        logging.info(f"✅ [KEEP-ALIVE] Server ping successful")
                    else:
                        logging.warning(f"⚠️ [KEEP-ALIVE] Unexpected status: {r.status_code}")
                except requests.Timeout:
                    logging.warning(f"⏱️ [KEEP-ALIVE] Server ping timeout")
                except Exception as e:
                    logging.warning(f"⚠️ [KEEP-ALIVE] Error: {e}")
            
            # Every 10 cycles (50 minutes), clean up old sessions
            counter += 1
            if counter >= 10:
                counter = 0
                try:
                    with shared_lock:
                        sessions = load_json(SESSIONS_FILE, {})
                        before = len(sessions)
                        now = datetime.now().timestamp()
                        # Remove sessions older than 24 hours
                        sessions = {k: v for k, v in sessions.items() if now - v.get("timestamp", now) < 86400}
                        save_json(SESSIONS_FILE, sessions)
                        after = len(sessions)
                        logging.info(f"🧹 [CLEANUP] Sessions: {before} → {after}")
                except Exception as e:
                    logging.error(f"❌ [CLEANUP ERROR]: {e}")
        except Exception as e:
            logging.error(f"❌ [KEEP-ALIVE ERROR]: {e}")
            time.sleep(60)  # Wait before retrying

def shutdown():
    """Graceful shutdown"""
    logging.info("🛑 [SHUTDOWN] Shutting down gracefully...")
    try:
        whatsapp_executor.shutdown(wait=True)
        logging.info("✅ [SHUTDOWN] Thread pool shutdown complete")
    except Exception as e:
        logging.error(f"❌ [SHUTDOWN ERROR]: {e}")

atexit.register(shutdown)

if __name__ == "__main__":
    # Start keep-alive thread
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    logging.info("🚀 [START] VIP Numbers Bot started successfully")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
