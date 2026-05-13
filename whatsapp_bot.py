import os, sys, json, logging, random, re, requests, threading, functools, html, time, atexit
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
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: pass
    return {}

CFG = get_config()

def _digits_only(s):
    return "".join(filter(str.isdigit, str(s or "")))

def normalize_whatsapp_phone(raw):
    """Digits-only id for Cloud API (Morocco: 212…)."""
    d = _digits_only(raw)
    if not d:
        return ""
    if d.startswith("212"):
        return d
    if d.startswith("0") and len(d) >= 10:
        return "212" + d[1:]
    if len(d) == 9:
        return "212" + d
    return d

ACCESS_TOKEN    = os.environ.get("ACCESS_TOKEN") or CFG.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID") or CFG.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN") or CFG.get("VERIFY_TOKEN", "vip_bot_2026")
ADMIN_PHONE     = normalize_whatsapp_phone(os.environ.get("ADMIN_PHONE") or CFG.get("ADMIN_PHONE", "212625489153"))
_default_catalog = "https://vip-boti.onrender.com"
CATALOG_URL     = (os.environ.get("CATALOG_URL") or CFG.get("CATALOG_URL") or _default_catalog).rstrip("/")
DASHBOARD_USER  = os.environ.get("DASHBOARD_USER") or CFG.get("DASHBOARD_USER", "admin")
DASHBOARD_PASS  = os.environ.get("DASHBOARD_PASS") or CFG.get("DASHBOARD_PASS", "vip2026")
API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# ============================================================
# 📋  LOGGING
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

shared_lock = threading.Lock()
# Use OrderedDict for processed_messages to avoid unbounded growth (LRU cache)
processed_messages = OrderedDict()
MAX_PROCESSED_MESSAGES = 1000  # Keep only last 1000 message IDs in memory

# Thread pool for WhatsApp sending (prevents thread explosion)
whatsapp_executor = ThreadPoolExecutor(max_workers=5)

def load_json(path, default):
    with shared_lock:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
    return default

def save_json(path, data):
    with shared_lock:
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
    r'(?:\b(?:num(?:ero)?|nimiro|nemiro|nomero|numero|número)\b[\s:,-]*)?'  # optional local keyword
    r'(?:(?:\+?212|00212)[\s./-]?)?'   # optional country code: +212, 212, 00212
    r'(?:0?)([5-7])[\s./-]?(\d{1,2})[\s./-]?(\d{1,2})[\s./-]?(\d{1,2})[\s./-]?(\d{1,2})'
)

def _extract_moroccan_numbers(text):
    """Extract all plausible Moroccan mobile numbers from text, return as 10-digit strings."""
    candidates = []
    for m in _MOROCCAN_PHONE_RE.finditer(text):
        raw = ''.join(m.groups())
        digits = ''.join(filter(str.isdigit, raw))
        if len(digits) == 9:
            digits = "0" + digits
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
    Find a VIP number from user text. Bypasses strict catalog validation.
    Returns: (item, tier) or (None, None)
    """
    catalog = load_json(CATALOG_FILE, {})
    candidates = _extract_moroccan_numbers(text)
    if not candidates:
        return None, None
    
    candidate = candidates[0]
    
    # Try to find in catalog for actual price/tier
    for tier, items in catalog.items():
        for item in items:
            item_digits = "".join(filter(str.isdigit, item["number"]))
            # Match: full 10-digit, or last 9 digits
            if candidate == item_digits or candidate[1:] == item_digits[1:]:
                return item, tier
                
    # If not in catalog, accept it anyway (TASK 3)
    formatted = f"{candidate[:2]} {candidate[2:4]} {candidate[4:6]} {candidate[6:8]} {candidate[8:]}"
    return {"number": formatted, "price": "غير محدد", "status": "available", "tier": "Custom"}, "Custom"

def is_direct_number_query(text):
    """
    Detect if user is directly asking about or mentioning a specific number.
    Returns True if text contains Arabic/French/English number query keywords.
    """
    t = text.lower()
    # Keywords indicating direct number inquiry: "رقم", "عندك", "كاين", "donne", "envoie", "nomero"
    direct_keywords = [
        "رقم", "عندك", "كاين", "ديالكم", "ديالنا",
        "donne", "envoie", "nomero", "numero", "give", "send", "have",
        "num", "nimiro", "nemiro", "nmira"
    ]
    return any(kw in t for kw in direct_keywords)

def format_catalog_message():
    catalog = load_json(CATALOG_FILE, {})
    
    # إذا كان الكتالوج فارغ — رد تنبيه
    if not catalog:
        return "⚠️ الكتالوج فارغ دابا — أضف نوامر دابا باش تشوفهم هنا! 📋"
    
    lines = ["🌟 *أرقام VIP المتوفرة حالياً:* \n"]
    has_available = False
    
    for tier, items in catalog.items():
        available = [i for i in items if i.get("status", "available") == "available"]
        if not available: continue
        has_available = True
        lines.append(f"🔹 *{tier.upper()}:*")
        for item in available:
            lines.append(f"  📱 {item['number']} — *{item.get('price', 'N/A')}*")
        lines.append("")
    
    # إذا ما كاينش نوامر متوفرين
    if not has_available:
        return "😕 ما كاينش نوامر متوفرين دابا — خاصك تتصل بينا مباشرة! 📞"
    
    lines.append(f"🌐 شوف الكتالوج كامل هنا: {CATALOG_URL}")
    lines.append("\nصيفط ليا الرقم اللي عجبك باش نكملو! 🚀")
    return "\n".join(lines)

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
    
    # --- PRIORITY 1: CATALOG (most important — prevents greeting override) ---
    for kw in CATALOG_KW:
        if kw in t: return "show_catalog"
    
    # --- PRIORITY 2: DIRECT NUMBER QUERY ---
    digits = "".join(filter(str.isdigit, t))
    if len(digits) >= 9 and is_direct_
