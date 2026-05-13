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
    if len(digits) >= 9 and is_direct_number_query(t):
        return "number_inquiry"
    
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

# ============================================================
def send_whatsapp(to, text):
    """Send WhatsApp message with timeout and error handling"""
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logging.error(f"❌ [SEND BLOCKED] Missing ACCESS_TOKEN or PHONE_NUMBER_ID")
        return False
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:4096]}}  # WhatsApp max 4096 chars
    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        logging.info(f"📲 [SEND] To: {to} | Status: {r.status_code}")
        if r.status_code not in (200, 201):
            logging.error(f"❌ [SEND FAIL] Status: {r.status_code} | {r.text[:500]}")
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
    return send_whatsapp(phone, msg)


def notify_admin_media(sender, media_type):
    if sender == ADMIN_PHONE:
        return
    media_label = "صورة/ملف" if media_type in ("image", "document", "audio", "video", "sticker") else "ميديا"
    alert = (
        "⚠️ الكليان صيفط صورة/ملف! شوفها فـ Meta Dashboard.\n"
        f"📞 من: {sender}\n"
        f"📎 النوع: {media_type} ({media_label})\n"
        f"🔗 https://wa.me/{sender}"
    )
    send_whatsapp_async(ADMIN_PHONE, alert)

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
        threading.Thread(target=send_whatsapp, args=(ADMIN_PHONE, "🔔 اختبار — الإشعارات خدامة! ✅")).start()
        return "✅ تم إرسال اختبار."
    return "🛠️ أمر غير معروف. صيفط `!help`"

# ============================================================
# 🧠  MAIN LOGIC — 100% responses.json, ZERO AI
# ============================================================
def _get_known_leads():
    return set(load_json(LEADS_FILE, []))

def _save_known_lead(sender):
    leads = _get_known_leads()
    leads.add(sender)
    save_json(LEADS_FILE, list(leads))

def handle_logic(sender, text):
    sessions = load_json(SESSIONS_FILE, {})
    raw_text = text.strip()

    # — NOTIFY ADMIN (Immediate, failure-safe) —
    if sender != ADMIN_PHONE:
        logging.info(f"🔔 [NOTIFY ADMIN] New message from {sender}")
        def _safe_admin_notify(phone, msg):
            try:
                send_whatsapp(phone, msg)
            except Exception as e:
                logging.error(f"❌ [ADMIN NOTIFY FAIL] {e}")
        threading.Thread(target=_safe_admin_notify, args=(ADMIN_PHONE, f"📩 *ميساج جديد من {sender}:*\n\"{raw_text}\"")).start()

    # — ADMIN: no lead/name flow; commands only (non-commands: clear stale session, no reply) —
    if sender == ADMIN_PHONE:
        if raw_text.startswith("!"):
            return handle_admin_command(sender, raw_text)
        sessions.pop(sender, None)
        save_json(SESSIONS_FILE, sessions)
        return None

    # — NEW LEAD / NAME REQUEST (first contact) —
    known = _get_known_leads()
    if sender not in known:
        _save_known_lead(sender)
        # TASK 1: Ghost Lead Capture (Immediate Admin Alert)
        threading.Thread(target=_safe_admin_notify, args=(ADMIN_PHONE, f"🚨 New Lead Clicked: {sender}\nرسالة: {raw_text}")).start()
        
        vip_item, tier = find_number_in_catalog(raw_text)
        
        if vip_item:
            sessions[sender] = {"step": "initial_name", "data": {}, "first_msg": raw_text, "vip_item": vip_item}
            _touch_session(sessions[sender])
            save_json(SESSIONS_FILE, sessions)
            return f"مرحبا بيك أخويا/أختي ✨\nسجلنا الرقم ديالك: {vip_item['number']} 🎯\nشنو الإسم الكريم باش نأكدو الطلب؟"
        else:
            sessions[sender] = {"step": "initial_name", "data": {}, "first_msg": raw_text}
            _touch_session(sessions[sender])
            save_json(SESSIONS_FILE, sessions)
            return pick_response("ask_name_initial")

    # — IMMEDIATE NUMBER VERIFICATION (before sessions/forms) —
    # Check if user is asking about a specific number (رقم، عندك، كاين، brit, etc)
    t_low = raw_text.lower()
    digits_in_text = "".join(filter(str.isdigit, t_low))
    if is_direct_number_query(t_low) and len(digits_in_text) >= 9:
        vip_item, tier = find_number_in_catalog(raw_text)
        if vip_item:
            sessions[sender] = {"step": "initial_name", "data": {}, "first_msg": raw_text, "vip_item": vip_item}
            _touch_session(sessions[sender])
            save_json(SESSIONS_FILE, sessions)
            return f"مرحبا بيك أخويا/أختي ✨\nسجلنا الرقم ديالك: {vip_item['number']} 🎯\nشنو الإسم الكريم باش نأكدو الطلب؟"
        else:
            return pick_response("number_not_found", catalog_url=CATALOG_URL)

    # — ORDER FORM FLOW —
    if sender in sessions and "step" in sessions[sender]:
        session = sessions[sender]
        step = session["step"]

        if step == "initial_name":
            name = raw_text
            session["data"]["name"] = name
            
            vip_item = session.get("vip_item")
            
            if vip_item:
                # Finalize order directly (TASK 3)
                city = "غير محدد"
                vip_num = vip_item["number"]
                orders = load_json(ORDERS_FILE, [])
                order_id = f"ORD-{datetime.now().strftime('%d%m%Y-%H%M%S')}"
                orders.append({
                    "id": order_id, "sender": sender, "vip_number": vip_num,
                    "price": vip_item.get("price", "N/A"),
                    "tier": vip_item.get("tier", ""),
                    "customer": {"name": name, "address": city, "phone": "whatsapp"},
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "pending"
                })
                save_json(ORDERS_FILE, orders)
                
                backup_summary = (
                    "🗂️ NEW ORDER FINALIZED\n"
                    f"sender={sender}\n"
                    f"number={vip_num}\n"
                    f"name={name}\n"
                    f"price={vip_item.get('price', 'N/A')}"
                )
                threading.Thread(target=_safe_admin_notify, args=(ADMIN_PHONE, backup_summary)).start()
                mark_number_sold(vip_num)
                
                sessions.pop(sender, None)
                save_json(SESSIONS_FILE, sessions)
                return pick_response("order_complete", number=vip_num, name=name, city=city)
            else:
                # No number picked yet, just welcome
                sessions.pop(sender, None)
                save_json(SESSIONS_FILE, sessions)
                return pick_response("welcome_with_name", name=name)

        if step == "address":
            city = raw_text
            vip_item = session.get("vip_item")
            if not vip_item:
                sessions.pop(sender, None)
                save_json(SESSIONS_FILE, sessions)
                return pick_response("unknown")
            od = session.get("data", {})
            name = od.get("name", "")
            vip_num = vip_item["number"]
            od["address"] = city
            orders = load_json(ORDERS_FILE, [])
            order_id = f"ORD-{datetime.now().strftime('%d%m%Y-%H%M%S')}"
            orders.append({
                "id": order_id, "sender": sender, "vip_number": vip_num,
                "price": vip_item.get("price", "N/A"),
                "tier": vip_item.get("tier", ""),
                "customer": {"name": name, "address": city, "phone": "whatsapp"},
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "pending"
            })
            save_json(ORDERS_FILE, orders)
            backup_summary = (
                "🗂️ BACKUP ORDER RAW\n"
                f"id={order_id}\n"
                f"sender={sender}\n"
                f"number={vip_num}\n"
                f"price={vip_item.get('price', 'N/A')}\n"
                f"tier={vip_item.get('tier', '')}\n"
                f"name={name}\n"
                f"city={city}\n"
                f"time={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_whatsapp(ADMIN_PHONE, backup_summary)
            mark_number_sold(vip_num)
            admin_msg = pick_response("admin_order", number=vip_num, name=name or "?", city=city or "?", phone="واتساب", sender=sender)
            send_whatsapp(ADMIN_PHONE, admin_msg)
            sessions.pop(sender, None)
            save_json(SESSIONS_FILE, sessions)
            return pick_response("order_complete", number=vip_num, name=name, city=city)

        if step == "confirm":
            t_low = raw_text.lower().strip()
            yes_w = ["نعم","aywa","oui","yes","واه","اه","ايوا","yep","ok","okay","بغيت","هيا","kayen","iyeh","wah"]
            no_w = ["لا","non","no","nope","ma bghitch","ما بغيتش","la"]
            vip = session["vip_item"]
            if any(w in t_low for w in yes_w):
                session["step"] = "initial_name"
                session["data"] = {}
                session["vip_item"] = vip
                _touch_session(session)
                sessions[sender] = session
                save_json(SESSIONS_FILE, sessions)
                return pick_response("confirm_yes", number=vip["number"])
            elif any(w in t_low for w in no_w):
                sessions.pop(sender, None)
                save_json(SESSIONS_FILE, sessions)
                return pick_response("confirm_no")
            else:
                return pick_response("confirm_unclear", number=vip["number"], price=vip.get("price", "200 DH"))

    # — CHECK FOR VIP NUMBER —
    vip_item, tier = find_number_in_catalog(raw_text)
    if vip_item:
        sessions[sender] = {"step": "confirm", "vip_item": vip_item, "data": {}}
        _touch_session(sessions[sender])
        save_json(SESSIONS_FILE, sessions)
        return pick_response("number_available", number=vip_item["number"], price=vip_item.get("price", "N/A"))

    # — INTENT DETECTION —
    intent = detect_intent(raw_text)

    if intent == "show_catalog":
        catalog_text = format_catalog_message()
        return pick_response("show_catalog", catalog=catalog_text)

    if intent == "number_inquiry":
        return pick_response("number_not_found")

    if intent == "contact_request":
        return pick_response("contact_request", catalog_url=CATALOG_URL)

    if intent in ("greeting", "price_inquiry", "help", "cancel", "thanks", "negotiation", "delivery_question", "trust_question", "unknown"):
        if intent == "cancel" and sender in sessions:
            sessions.pop(sender, None)
            save_json(SESSIONS_FILE, sessions)
        return pick_response(intent)

    return pick_response("unknown")

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
    # ── GET: Verification handshake ──────────────────────────────────────────
    if request.method == "GET":
        try:
            mode      = request.args.get("hub.mode")
            token     = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            verify_token = VERIFY_TOKEN  # already loaded at startup
            if mode and token:
                if mode == "subscribe" and token == verify_token:
                    logging.info("✅ [WEBHOOK] Verification successful!")
                    return challenge, 200
                else:
                    logging.warning(f"❌ [WEBHOOK] Invalid verify token received: '{token}'")
                    return "Forbidden", 403
            return "Webhook is active", 200
        except Exception as e:
            logging.error(f"❌ [WEBHOOK GET] Exception: {e}")
            return "Internal Server Error", 500

    # ── POST: Incoming message ───────────────────────────────────────────────
    try:
        data = request.get_json(force=True)
        logging.info(f"📥 [WEBHOOK RAW] {str(data)[:300]}...")

        if not (data and 'entry' in data):
            return "ok", 200

        changes = data['entry'][0].get('changes', [{}])
        value   = changes[0].get('value', {})
        messages = value.get('messages')
        if not messages:
            return "ok", 200

        msg    = messages[0]
        msg_id = msg.get('id', '')

        # ── De-duplicate: skip already-processed messages ──
        with shared_lock:
            if msg_id in processed_messages:
                logging.info(f"⏭️  [WEBHOOK] Already processed: {msg_id}")
                return "ok", 200
            # Mark as processed BEFORE handling (prevents race condition)
            processed_messages[msg_id] = True
            if len(processed_messages) > MAX_PROCESSED_MESSAGES:
                processed_messages.popitem(last=False)

        sender = "".join(filter(str.isdigit, msg['from']))

        # ── Alert admin about every non-admin message ──
        if sender != ADMIN_PHONE:
            if msg.get('type') == 'text':
                body_preview = msg['text']['body'][:100]
                alert_msg = (
                    f"🚨 رسالة جديدة من: {sender}\n"
                    f"الرسالة: {body_preview}\n"
                    f"تواصل: https://wa.me/{sender}"
                )
            else:
                alert_msg = (
                    f"🚨 ميديا جديدة من: {sender}\n"
                    f"النوع: {msg.get('type')}\n"
                    f"تواصل: https://wa.me/{sender}"
                )
            send_whatsapp_async(ADMIN_PHONE, alert_msg)
            logging.info(f"[SYSTEM] Lead alert sent to {ADMIN_PHONE} for {sender}")

        # ── Process message ──
        if msg.get('type') == 'text':
            reply = handle_logic(sender, msg['text']['body'])
            if reply:
                send_whatsapp_async(sender, reply)
        elif msg.get('type') in ('image', 'document', 'audio', 'video', 'sticker'):
            notify_admin_media(sender, msg.get('type'))
            reply = pick_response("media_received")
            if reply:
                send_whatsapp_async(sender, reply)

        return "ok", 200

    except Exception as e:
        logging.error(f"❌ [WEBHOOK POST ERROR]: {e}")
        import traceback
        logging.error(traceback.format_exc())
        # Always return 200 so Meta does not retry in a loop
        return "ok", 200
