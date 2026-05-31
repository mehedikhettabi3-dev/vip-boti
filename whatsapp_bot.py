"""
VIP Numbers Morocco — WhatsApp Bot v8.0
Agent: Nessrine | Experte Ventes 40 ans | AR / FR / EN
Architecture: NVIDIA NIM 2000 tokens + MongoDB + Self-Ping + Image Catalog
"""

import os, sys, re, json, logging, threading, random, time, requests
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from dotenv import load_dotenv

load_dotenv()
try:
    if sys.stdout.encoding != 'utf-8': sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8': sys.stderr.reconfigure(encoding='utf-8')
except Exception: pass

# ============================================================
# CONFIG
# ============================================================
ACCESS_TOKEN    = os.environ.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN", "vip_sales_secure_2026")
ADMIN_PHONE     = "".join(filter(str.isdigit, os.environ.get("ADMIN_PHONE", "212778375026")))
NVIDIA_API_KEY  = os.environ.get("NVIDIA_API_KEY", "")
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY", "")
MONGODB_URI     = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI", "")
MONGO_DB_NAME   = os.environ.get("MONGO_DB_NAME", "vip_numbers_bot")
SERVICE_URL     = os.environ.get("CATALOG_URL", "https://vip-boti.onrender.com").rstrip("/")
META_API_URL    = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

# Error fallback message (sent when bot crashes)
ERROR_FALLBACK = (
    "السلام عليكم 👋\n\n"
    "بسبب كثرة الرسائل حالياً، نعتذر عن وجود عطل تقني مؤقت.\n\n"
    "يمكنكم التواصل مباشرة على الرقم:\n"
    "📞 *07 78 37 50 26*\n\n"
    "وسنرد عليكم في أقرب وقت ممكن. شكراً على تفهمكم 🙏"
)

# ============================================================
# LOGGING
# ============================================================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
_log_path = os.path.join(BASE_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(_log_path, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
    ]
)

app      = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)
executor = ThreadPoolExecutor(max_workers=8)
_lock    = threading.Lock()
processed_ids = OrderedDict()

# ============================================================
# MONGODB — Lazy singleton with file fallback
# ============================================================
_mongo_db = None

def get_db():
    global _mongo_db
    if _mongo_db is not None:
        return _mongo_db
    if not MONGODB_URI:
        return None
    try:
        from pymongo import MongoClient
        client   = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        client.admin.command("ping")
        _mongo_db = client[MONGO_DB_NAME]
        # TTL index: sessions auto-expire after 24 h
        try:
            _mongo_db.sessions.create_index("updated_at", expireAfterSeconds=86400)
        except Exception: pass
        logging.info("✅ [MONGO] Connected to MongoDB Atlas")
        return _mongo_db
    except Exception as e:
        logging.error(f"❌ [MONGO] {e}")
        return None

# ============================================================
# PERSISTENCE HELPERS — MongoDB primary, file fallback
# ============================================================
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
LEADS_FILE    = os.path.join(BASE_DIR, "known_leads.json")
ORDERS_FILE   = os.path.join(BASE_DIR, "orders.json")

def _fload(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception: pass
    return default

def _fsave(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[FILE SAVE] {path}: {e}")

def load_session(sender):
    db = get_db()
    if db:
        try:
            doc = db.sessions.find_one({"sender": sender})
            if doc:
                doc.pop("_id", None)
                return doc
            return {}
        except Exception as e:
            logging.warning(f"[SESSION LOAD] Mongo fail: {e}")
    return _fload(SESSIONS_FILE, {}).get(sender, {})

def save_session(sender, data):
    db = get_db()
    if db:
        try:
            db.sessions.update_one(
                {"sender": sender},
                {"$set": {**data, "sender": sender, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            return
        except Exception as e:
            logging.warning(f"[SESSION SAVE] Mongo fail: {e}")
    sessions = _fload(SESSIONS_FILE, {})
    sessions[sender] = data
    _fsave(SESSIONS_FILE, sessions)

def delete_session(sender):
    db = get_db()
    if db:
        try:
            db.sessions.delete_one({"sender": sender})
            return
        except Exception: pass
    sessions = _fload(SESSIONS_FILE, {})
    sessions.pop(sender, None)
    _fsave(SESSIONS_FILE, sessions)

def is_known_lead(sender):
    db = get_db()
    if db:
        try:
            return db.leads.find_one({"sender": sender}) is not None
        except Exception: pass
    return sender in set(_fload(LEADS_FILE, []))

def save_lead(sender, first_msg=""):
    db = get_db()
    if db:
        try:
            db.leads.update_one(
                {"sender": sender},
                {"$setOnInsert": {"sender": sender, "first_msg": first_msg, "first_seen": datetime.utcnow()}},
                upsert=True
            )
            return
        except Exception: pass
    leads = set(_fload(LEADS_FILE, []))
    leads.add(sender)
    _fsave(LEADS_FILE, list(leads))

def save_order(order):
    db = get_db()
    if db:
        try:
            db.orders.insert_one(order)
            return
        except Exception: pass
    orders = _fload(ORDERS_FILE, [])
    orders.append(order)
    _fsave(ORDERS_FILE, orders)

def get_stats():
    db = get_db()
    if db:
        try:
            return {
                "leads":    db.leads.count_documents({}),
                "sessions": db.sessions.count_documents({}),
                "orders":   db.orders.count_documents({})
            }
        except Exception: pass
    return {
        "leads":    len(_fload(LEADS_FILE, [])),
        "sessions": len(_fload(SESSIONS_FILE, {})),
        "orders":   len(_fload(ORDERS_FILE, []))
    }

# ============================================================
# CATALOG HELPERS
# ============================================================
CATALOG_FILE = os.path.join(BASE_DIR, "catalog.json")

def load_catalog():
    return _fload(CATALOG_FILE, {})

def save_catalog(c):
    _fsave(CATALOG_FILE, c)

def get_all_numbers():
    catalog = load_catalog()
    nums = []
    for tier, items in catalog.items():
        for item in items:
            nums.append({**item, "tier": tier})
    return nums

_PHONE_RE = re.compile(
    r'(?:\+?212|00212|0)[\s./-]?([5-7][\s./-]?\d[\s./-]?\d[\s./-]?\d[\s./-]?\d[\s./-]?\d[\s./-]?\d[\s./-]?\d[\s./-]?\d)'
)

def find_vip_number(text):
    """Extract phone number from text and find it in catalog. Returns (item, tier) or (None, None)."""
    m = _PHONE_RE.search(text)
    if not m: return None, None
    raw    = m.group(0)
    digits = "".join(filter(str.isdigit, raw))
    if digits.startswith("212"): digits = "0" + digits[3:]
    if len(digits) != 10: return None, None

    catalog = load_catalog()
    for tier, items in catalog.items():
        for item in items:
            item_d = "".join(filter(str.isdigit, item["number"]))
            if digits == item_d or digits[1:] == item_d[1:]:
                return {**item, "tier": tier}, tier

    # Valid but not in catalog
    fmt = f"{digits[:2]} {digits[2:4]} {digits[4:6]} {digits[6:8]} {digits[8:]}"
    return {"number": fmt, "price": "غير محدد", "status": "available", "tier": "Custom"}, "Custom"

def format_catalog_text():
    catalog = load_catalog()
    if not catalog:
        return "⚠️ الكتالوج فارغ حالياً."
    ICONS  = {"Diamond": "💎", "Gold": "⭐", "Silver": "✨"}
    LABELS = {"Diamond": "SUPER VIP — 150 DH", "Gold": "VIP — 135 DH", "Silver": "VIP — 100 DH"}
    lines  = ["🌟 *أرقام VIP المتوفرة:*\n"]
    for tier, items in catalog.items():
        avail = [i for i in items if i.get("status", "available") == "available"]
        if not avail: continue
        icon  = ICONS.get(tier, "🔹")
        label = LABELS.get(tier, tier)
        lines.append(f"{icon} *{label}:*")
        for item in avail[:10]:
            lines.append(f"  📱 `{item['number']}`")
        lines.append("")
    lines.append("الدفع عند الاستلام ✅ | التوصيل لجميع مدن المغرب 🇲🇦")
    return "\n".join(lines)

def mark_sold(number_str):
    catalog  = load_catalog()
    digits   = "".join(filter(str.isdigit, str(number_str)))
    found    = False
    for tier, items in catalog.items():
        for item in items:
            item_d = "".join(filter(str.isdigit, item["number"]))
            if item_d == digits or item_d[1:] == digits[1:]:
                item["status"] = "sold"
                found = True
    if found: save_catalog(catalog)
    return found

# Catalog image URLs (served from Flask /static/)
CATALOG_IMAGES = {
    "Diamond": f"{SERVICE_URL}/static/vip_150dh.jpg",
    "Gold":    f"{SERVICE_URL}/static/vip_135dh.jpg",
    "Silver":  f"{SERVICE_URL}/static/vip_100dh.jpg",
}

# ============================================================
# WHATSAPP SEND
# ============================================================
def _send_wa(to, payload):
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logging.error("[SEND] Missing ACCESS_TOKEN or PHONE_NUMBER_ID")
        return False
    try:
        r = requests.post(
            META_API_URL,
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={**payload, "messaging_product": "whatsapp", "to": to},
            timeout=15
        )
        ok = r.status_code in (200, 201)
        if not ok:
            logging.error(f"[SEND FAIL] {r.status_code} → {r.text[:300]}")
        return ok
    except Exception as e:
        logging.error(f"[SEND ERROR] {e}")
        return False

def send_text(to, text):
    return _send_wa(to, {"type": "text", "text": {"body": text[:4096]}})

def send_image(to, url, caption=""):
    return _send_wa(to, {"type": "image", "image": {"link": url, "caption": caption[:1024]}})

def send_text_async(to, text):   executor.submit(send_text,  to, text)
def send_image_async(to, url, caption=""): executor.submit(send_image, to, url, caption)

# ============================================================
# AI ENGINE — Nessrine (NVIDIA NIM → Groq → static fallback)
# ============================================================
NESSRINE_SYSTEM = """أنتِ نسرين، خبيرة مبيعات محترفة في "VIP Numbers Morocco" بخبرة 40 سنة.
تتحدثين بثلاث لغات بطلاقة تامة: الدارجة المغربية 🇲🇦 | الفرنسية 🇫🇷 | الإنجليزية 🇬🇧
(تكيفي لغتكِ تلقائياً مع لغة العميل)

🎯 مهمتكِ الوحيدة: إقناع العميل وإتمام البيع باحترافية ودفء حقيقي.
✨ أسلوبكِ: طبيعي، حار، مقنع — مثل محادثة WhatsApp بين أشخاص يثقون ببعضهم.
🚫 ممنوع تماماً: الأسلوب الآلي أو الردود العامة أو الجمل الطويلة الفارغة.

💰 الأسعار النهائية (لا خصومات):
• 💎 150 درهم — أرقام SUPER VIP (أرقام مكررة رباعية كـ 2222 أو 8888)
• ⭐ 135 درهم — أرقام VIP مميزة (أرقام مكررة ثلاثية كـ 777 أو 888)
• ✨ 100 درهم — أرقام VIP جميلة

✅ الدفع عند الاستلام دائماً — التوصيل لجميع مدن المغرب 🇲🇦
🚫 لا تختلقي أرقاماً. تحدثي فقط عن أرقام الكتالوج.
📦 عند طلب الشراء: اجمعي الاسم + المدينة + رقم التواصل لتأكيد الطلب.
⚡ ردودكِ: قصيرة (1-3 جمل). مؤثرة. إيموجي طبيعية. لا حشو."""


def _build_messages(sender, user_msg, session):
    catalog = load_catalog()
    tier_summary = " | ".join(
        f"{tier}({len([i for i in items if i.get('status','available')=='available'])} متوفر بـ"
        f"{'150' if tier=='Diamond' else '135' if tier=='Gold' else '100'}دh)"
        for tier, items in catalog.items()
    )
    system = NESSRINE_SYSTEM + f"\n\n📦 الكتالوج الحالي: {tier_summary}"

    messages = [{"role": "system", "content": system}]

    # Last 5 exchanges from history
    for h in session.get("history", [])[-5:]:
        if h.get("user"): messages.append({"role": "user",      "content": h["user"]})
        if h.get("bot"):  messages.append({"role": "assistant", "content": h["bot"]})

    messages.append({"role": "user", "content": user_msg})
    return messages


def ask_nvidia(messages):
    if not NVIDIA_API_KEY: return None
    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "meta/llama-3.3-70b-instruct",
                "messages": messages,
                "temperature": 0.75,
                "max_tokens": 2000,
                "top_p": 0.9
            },
            timeout=25
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        logging.warning(f"[NVIDIA] {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logging.error(f"[NVIDIA ERROR] {e}")
    return None


def ask_groq(messages):
    if not GROQ_API_KEY: return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024
            },
            timeout=15
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        logging.warning(f"[GROQ] {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logging.error(f"[GROQ ERROR] {e}")
    return None


def nessrine_reply(sender, user_msg, session):
    """Primary: NVIDIA NIM (2000 tokens) → Fallback: Groq → None"""
    msgs = _build_messages(sender, user_msg, session)
    reply = ask_nvidia(msgs)
    if reply:
        logging.info(f"[AI:NVIDIA] ✅ replied for {sender}")
        return reply
    reply = ask_groq(msgs)
    if reply:
        logging.info(f"[AI:GROQ] ✅ fallback for {sender}")
        return reply
    logging.warning(f"[AI] All engines failed for {sender}")
    return None


def update_history(session, user_msg, bot_reply):
    history = session.get("history", [])
    history.append({"user": user_msg, "bot": bot_reply})
    if len(history) > 10:
        history = history[-10:]
    session["history"] = history
    return session

# ============================================================
# ORDER FLOW STATE MACHINE
# ============================================================
_CANCEL_W = {"لا", "non", "no", "cancel", "stop", "إلغاء", "annuler", "مابغيتش", "خلاص", "bghit_annuler"}


def run_order_flow(sender, text, session):
    step = session.get("step")
    data = session.get("data", {})
    t    = text.strip()
    tl   = t.lower()

    # Cancel allowed on any step except ask_phone (where "لا" = no contact number)
    if step != "ask_phone" and any(w in tl.split() for w in _CANCEL_W):
        delete_session(sender)
        return "واخا خويا 😊 الطلب ألغينا. إلا بغيتي شي حاجة أخرى، أنا هنا دايماً! 🌟"

    if step == "ask_name":
        data["name"] = t
        session["data"] = data
        session["step"] = "ask_city"
        save_session(sender, session)
        return f"أهلاً {t}! 🌟\nفي أي مدينة تسكن؟ 📍"

    if step == "ask_city":
        data["city"] = t
        session["data"] = data
        session["step"] = "ask_phone"
        save_session(sender, session)
        return "آخر خطوة — رقم هاتفك للتواصل 📞\n(صيفط *لا* إلا كانك ما بغيتيش)"

    if step == "ask_phone":
        data["contact_phone"] = "واتساب" if tl in {"لا", "no", "non", "la"} else t

        order_id = f"VIP-{datetime.now().strftime('%d%m%Y-%H%M%S')}-{random.randint(100, 999)}"
        vip      = session.get("vip_item", {})
        order    = {
            "id":         order_id,
            "sender":     sender,
            "vip_number": vip.get("number", ""),
            "price":      vip.get("price", ""),
            "tier":       vip.get("tier", ""),
            "customer":   {
                "name":  data.get("name", ""),
                "city":  data.get("city", ""),
                "phone": data.get("contact_phone", "")
            },
            "time":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending"
        }
        save_order(order)
        mark_sold(vip.get("number", ""))

        # Immediate admin alert
        alert = (
            f"🎉 *طلب جديد — VIP Numbers!*\n"
            f"📱 الرقم: *{vip.get('number', '')}* — {vip.get('price', '')}\n"
            f"👤 الاسم: {data.get('name', '')}\n"
            f"📍 المدينة: {data.get('city', '')}\n"
            f"📞 تواصل: {data.get('contact_phone', '')}\n"
            f"🆔 الطلب: {order_id}\n"
            f"🔗 https://wa.me/{sender}"
        )
        executor.submit(send_text, ADMIN_PHONE, alert)
        delete_session(sender)

        return (
            f"✅ *تم تأكيد طلبك!* 🎉\n\n"
            f"📱 الرقم: *{vip.get('number', '')}*\n"
            f"👤 الاسم: {data.get('name', '')}\n"
            f"📍 المدينة: {data.get('city', '')}\n"
            f"💰 الثمن: {vip.get('price', '')}\n\n"
            f"🚚 سنتصل بك قريباً لتأكيد التوصيل!\n"
            f"شكراً على ثقتك خويا 💛"
        )
    return None

# ============================================================
# CATALOG IMAGE SENDING
# ============================================================
TIER_CONFIG = [
    ("Diamond", "💎 *أرقام SUPER VIP — 150 درهم*\nأرقام متكررة رباعية ونادرة ⭐"),
    ("Gold",    "⭐ *أرقام VIP مميزة — 135 درهم*\nأرقام ثلاثية التكرار ومطلوبة 🔥"),
    ("Silver",  "✨ *أرقام VIP — 100 درهم*\nأرقام جميلة بثمن مناسب 💫"),
]


def send_catalog_images(sender):
    """Send catalog images (one per tier) with number lists in caption"""
    catalog   = load_catalog()
    sent_any  = False

    for tier, caption_header in TIER_CONFIG:
        items   = catalog.get(tier, [])
        avail   = [i for i in items if i.get("status", "available") == "available"]
        if not avail: continue

        nums_txt = "\n".join(f"  📱 {i['number']}" for i in avail[:10])
        full_cap = f"{caption_header}\n\n{nums_txt}\n\n✅ الدفع عند الاستلام | 🇲🇦 التوصيل لجميع المدن"
        img_url  = CATALOG_IMAGES.get(tier)

        if img_url:
            ok = send_image(sender, img_url, full_cap)
            if not ok:
                send_text(sender, full_cap)
        else:
            send_text(sender, full_cap)

        sent_any = True
        time.sleep(0.8)

    if sent_any:
        time.sleep(0.5)
        send_text(sender,
            "📌 صيفط ليا الرقم اللي عجبك وغنكمل معك الطلب في ثوانٍ! 🚀\n"
            "الدفع عند الاستلام ✅ — ما كتخلص حتى تشد الرقم فيدك 🤝"
        )
    else:
        send_text(sender, "⚠️ الكتالوج فارغ حالياً. تواصل معنا مباشرة على 07 78 37 50 26 📞")

# ============================================================
# FAST INTENT (no AI, instant routing)
# ============================================================
_RE_CATALOG  = re.compile(r'\b(نوامر|أرقام|ارقام|كتالوج|catalog|catalogue|nwamer|nwamar|nmari|'
                           r'liste|warini|عرض|ورينا|واش\s*كاين|الجديد|les\s*num|show\s*me)\b', re.I)
_RE_GREETING = re.compile(r'\b(سلام|السلام|مرحبا|أهلا|اهلا|hi|hello|bonjour|salut|salam|slm|hey|cv|labas)\b', re.I)
_RE_PRICE    = re.compile(r'\b(ثمن|بشحال|prix|price|combien|شحال|thaman|bch7al)\b', re.I)
_RE_TRUST    = re.compile(r'\b(مضمون|serious|sérieux|arnaque|ثقة|واش\s*حقيقي|legit|bsa7)\b', re.I)
_RE_DELIVERY = re.compile(r'\b(توصيل|livraison|delivery|tawsil|kifach\s*tawsil)\b', re.I)
_RE_THANKS   = re.compile(r'\b(شكرا|شكراً|merci|thanks|choukran|mrc)\b', re.I)


def quick_intent(text):
    t = text.strip()
    if _RE_CATALOG.search(t):  return "catalog"
    if _RE_PRICE.search(t):    return "price"
    if _RE_TRUST.search(t):    return "trust"
    if _RE_DELIVERY.search(t): return "delivery"
    if _RE_THANKS.search(t):   return "thanks"
    if _RE_GREETING.search(t): return "greeting"
    return None

# ============================================================
# ADMIN COMMANDS
# ============================================================
def handle_admin(sender, text):
    parts = text.strip().lower().split()
    if not parts: return "Admin mode ✅"
    cmd = parts[0]

    if cmd == "!help":
        return (
            "🛠️ *Commandes Admin Nessrine v8:*\n"
            "• `!stats` — Statistiques complètes\n"
            "• `!sold [num]` — Marquer vendu\n"
            "• `!add [num] [tier] [prix]` — Ajouter numéro\n"
            "• `!del [num]` — Supprimer numéro\n"
            "• `!reset` — Reset sessions\n"
            "• `!test` — Test notification admin\n"
            "• `!catalog` — Voir catalogue texte\n"
            "• `!img [num_wa]` — Envoyer images catalog\n"
        )

    if cmd == "!stats":
        nums  = get_all_numbers()
        avail = sum(1 for n in nums if n.get("status", "available") == "available")
        sold  = sum(1 for n in nums if n.get("status") == "sold")
        s     = get_stats()
        return (
            f"📊 *Stats Nessrine v8:*\n"
            f"✅ Disponibles: {avail}\n"
            f"❌ Vendus: {sold}\n"
            f"👥 Leads: {s['leads']}\n"
            f"📋 Commandes: {s['orders']}\n"
            f"⏳ Sessions actives: {s['sessions']}\n"
            f"🤖 NVIDIA: {'✅' if NVIDIA_API_KEY else '❌'}\n"
            f"🔄 Groq: {'✅' if GROQ_API_KEY else '❌'}\n"
            f"🍃 MongoDB: {'✅' if get_db() else '📁 file'}"
        )

    if cmd == "!catalog":
        return format_catalog_text()

    if cmd == "!img" and len(parts) > 1:
        target = "".join(filter(str.isdigit, " ".join(parts[1:])))
        if not target.startswith("212"):
            target = "212" + target.lstrip("0")
        executor.submit(send_catalog_images, target)
        return f"📸 Images envoyées à {target}"

    if cmd == "!sold" and len(parts) > 1:
        target = "".join(filter(str.isdigit, " ".join(parts[1:])))
        ok = mark_sold(target)
        return f"✅ Marqué vendu: {target}" if ok else f"❌ Introuvable: {target}"

    if cmd in ("!del", "!delete") and len(parts) > 1:
        target  = "".join(filter(str.isdigit, " ".join(parts[1:])))
        catalog = load_catalog()
        deleted = False
        for tier in catalog:
            before = len(catalog[tier])
            catalog[tier] = [i for i in catalog[tier]
                             if "".join(filter(str.isdigit, i["number"])) != target]
            if len(catalog[tier]) < before: deleted = True
        if deleted:
            save_catalog(catalog)
            return f"🗑️ Supprimé: {target}"
        return f"❌ Introuvable: {target}"

    if cmd == "!add" and len(parts) >= 4:
        num, tier, price = parts[1], parts[2].capitalize(), " ".join(parts[3:])
        catalog = load_catalog()
        if tier not in catalog: catalog[tier] = []
        d = "".join(filter(str.isdigit, num))
        fmt = f"{d[:2]} {d[2:4]} {d[4:6]} {d[6:8]} {d[8:]}" if len(d) == 10 else num
        catalog[tier].append({"number": fmt, "price": price, "status": "available"})
        save_catalog(catalog)
        return f"✅ Ajouté: {fmt} → {tier} ({price})"

    if cmd == "!reset":
        db = get_db()
        if db:
            try: db.sessions.delete_many({})
            except Exception: pass
        _fsave(SESSIONS_FILE, {})
        return "♻️ Sessions réinitialisées."

    if cmd == "!test":
        executor.submit(send_text, ADMIN_PHONE,
            "🔔 *Test Nessrine v8* — Bot actif ✅\nNVIDIA NIM + MongoDB + Keep-Alive")
        return "✅ Notification test envoyée."

    return f"❓ Commande inconnue: `{cmd}` — tape `!help`"

# ============================================================
# STATIC FALLBACK REPLIES
# ============================================================
STATIC = {
    "greeting": [
        "أهلاً وسهلاً! 🌟 أنا نسرين من *VIP Numbers Morocco* 👑\nصيفط *نوامر* باش تشوف الأرقام المتوفرة! 📱",
        "مرحبا بيك خويا! 😊 أنا نسرين، هنا لمساعدتك تلقى رقمك المثالي 💎\nشوف الكتالوج بـ *نوامر*! 🚀",
        "Bonjour! 👋 Je suis Nessrine de VIP Numbers Morocco 🇲🇦\nTapez *numéros* pour voir notre catalogue! 📋"
    ],
    "price": [
        "💰 أسعارنا:\n• 💎 *150 DH* — أرقام SUPER VIP (رباعية التكرار)\n• ⭐ *135 DH* — أرقام VIP مميزة\n• ✨ *100 DH* — أرقام VIP جميلة\n\nالدفع عند الاستلام ✅",
    ],
    "trust": [
        "✅ نخدمو منذ سنوات والحمدلله! الدفع عند الاستلام — ما كتخلص حتى تشد الرقم فيدك 🤝\nكلينا راضيين والحمدلله! 💛",
    ],
    "delivery": [
        "🚚 كنوصلو لجميع مدن المغرب! الدفع عند الاستلام ✅\nفين تسكن؟ نقدرو نشوف ليك التوصيل 📍",
    ],
    "thanks": [
        "الله يبارك فيك خويا! 😊 ديما في الخدمة 💛",
        "العفو خويا! 🌟 إلا احتجت شي حاجة أخرى، أنا هنا! 😊",
    ],
}


def _static(intent):
    opts = STATIC.get(intent, ["مرحبا! 🌟 صيفط *نوامر* باش تشوف الأرقام المتوفرة! 📱"])
    return random.choice(opts)

# ============================================================
# MAIN LOGIC
# ============================================================
def handle_logic(sender, text):
    try:
        raw = text.strip()
        if not raw: return None

        # ── ADMIN ────────────────────────────────────────────
        if sender == ADMIN_PHONE:
            return handle_admin(sender, raw) if raw.startswith("!") else None

        # ── ADMIN ALERT — every non-admin message ────────────
        def _alert():
            try:
                send_text(ADMIN_PHONE,
                    f"📩 *رسالة جديدة*\n"
                    f"📞 {sender}\n"
                    f"💬 \"{raw[:150]}\"\n"
                    f"🔗 https://wa.me/{sender}"
                )
            except Exception as e:
                logging.error(f"[ADMIN ALERT] {e}")
        executor.submit(_alert)

        # ── LOAD SESSION ─────────────────────────────────────
        session = load_session(sender)

        # ── NEW LEAD ─────────────────────────────────────────
        is_new = not is_known_lead(sender)
        if is_new:
            save_lead(sender, raw)
            # Check if first message contains a VIP number
            vip_item, _ = find_vip_number(raw)
            if vip_item and vip_item.get("status") == "available":
                session = {"step": "ask_name", "data": {}, "vip_item": vip_item, "history": []}
                save_session(sender, session)
                ai_reply = nessrine_reply(
                    sender,
                    f"عميل جديد أول رسالة له — يريد الرقم {vip_item['number']} بـ{vip_item['price']}. رحبي به بحرارة وأكدي توفر الرقم ثم اسأليه عن اسمه الكريم.",
                    session
                )
                if not ai_reply:
                    ai_reply = (
                        f"أهلاً وسهلاً بيك! 🌟\n"
                        f"الرقم *{vip_item['number']}* متوفر بـ *{vip_item['price']}* فقط — اختيار رائع! 💎\n"
                        f"شنو سميتك الكريمة؟ 🖊️"
                    )
                update_history(session, raw, ai_reply)
                save_session(sender, session)
                return ai_reply
            else:
                session = {"history": []}
                save_session(sender, session)
                ai_reply = nessrine_reply(sender, raw, session)
                if not ai_reply:
                    ai_reply = _static("greeting")
                update_history(session, raw, ai_reply)
                save_session(sender, session)
                return ai_reply

        # ── ACTIVE ORDER FLOW ─────────────────────────────────
        if session.get("step") in ("ask_name", "ask_city", "ask_phone"):
            reply = run_order_flow(sender, raw, session)
            if reply: return reply

        # ── VIP NUMBER DETECTED ───────────────────────────────
        vip_item, _ = find_vip_number(raw)
        if vip_item:
            if vip_item.get("status") == "sold":
                ai_reply = nessrine_reply(
                    sender,
                    f"العميل يسأل عن الرقم {vip_item['number']} لكنه مباع. اعتذري بأسلوب راقٍ واقترحي عليه أرقاماً مشابهة من الكتالوج.",
                    session
                )
                if not ai_reply:
                    ai_reply = (
                        f"معذرة خويا 😅 الرقم *{vip_item['number']}* تبيع للتو!\n"
                        f"عندنا أرقام مميزة أخرى — صيفط *نوامر* باش تشوف الكتالوج 📋"
                    )
                update_history(session, raw, ai_reply)
                save_session(sender, session)
                return ai_reply

            # Available → start order
            session["step"]     = "ask_name"
            session["data"]     = {}
            session["vip_item"] = vip_item
            session.setdefault("history", [])
            save_session(sender, session)

            ai_reply = nessrine_reply(
                sender,
                f"العميل يريد الرقم {vip_item['number']} بـ{vip_item['price']}. أكدي توفره بحماس واسأليه عن اسمه.",
                session
            )
            if not ai_reply:
                ai_reply = (
                    f"ممتاز! 🎯 الرقم *{vip_item['number']}* متوفر بـ *{vip_item['price']}* فقط!\n"
                    f"الدفع عند الاستلام ✅ — شنو سميتك الكريمة؟ 🖊️"
                )
            update_history(session, raw, ai_reply)
            save_session(sender, session)
            return ai_reply

        # ── QUICK INTENT ──────────────────────────────────────
        intent = quick_intent(raw)

        if intent == "catalog":
            executor.submit(send_catalog_images, sender)
            return None  # Images sent by send_catalog_images

        # ── NESSRINE AI REPLY ─────────────────────────────────
        ai_reply = nessrine_reply(sender, raw, session)
        if ai_reply:
            update_history(session, raw, ai_reply)
            save_session(sender, session)
            return ai_reply

        # ── STATIC FALLBACK ───────────────────────────────────
        reply = _static(intent or "greeting")
        update_history(session, raw, reply)
        save_session(sender, session)
        return reply

    except Exception as e:
        logging.error(f"[HANDLE ERROR] sender={sender} text={text!r} error={e}", exc_info=True)
        return ERROR_FALLBACK

# ============================================================
# FLASK ROUTES
# ============================================================
@app.route("/", methods=["GET", "HEAD"])
def home():
    if request.method == "HEAD":
        return Response(status=200)
    stats = get_stats()
    return jsonify({
        "status":  "online",
        "agent":   "Nessrine — VIP Numbers Morocco",
        "version": "8.0",
        "ai":      "NVIDIA NIM 2000 tokens",
        "mongodb": "connected" if get_db() else "file-fallback",
        "leads":   stats["leads"],
        "orders":  stats["orders"]
    }), 200


@app.route("/health")
def health():
    db    = get_db()
    stats = get_stats()
    return jsonify({
        "status":  "ok",
        "agent":   "Nessrine v8.0",
        "mongodb": "connected" if db else "file-fallback",
        "nvidia":  "configured" if NVIDIA_API_KEY else "missing",
        "groq":    "configured" if GROQ_API_KEY else "missing",
        "keep_alive": True,
        "stats":   stats,
        "time":    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # ── GET: Meta verification ──
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logging.info("✅ [WEBHOOK] Meta verified")
            return challenge, 200
        return "Forbidden", 403

    # ── POST: Incoming message ──
    try:
        data = request.get_json(force=True, silent=True)
        if not data or "entry" not in data:
            return "ok", 200

        changes  = data["entry"][0].get("changes", [{}])
        value    = changes[0].get("value", {})
        messages = value.get("messages")
        if not messages:
            return "ok", 200

        msg    = messages[0]
        msg_id = msg.get("id", "")

        # Dedup
        with _lock:
            if msg_id in processed_ids:
                return "ok", 200
            processed_ids[msg_id] = True
            if len(processed_ids) > 2000:
                processed_ids.popitem(last=False)

        sender   = "".join(filter(str.isdigit, msg.get("from", "")))
        msg_type = msg.get("type", "")

        if msg_type == "text":
            body = msg["text"]["body"]

            def _process():
                reply = handle_logic(sender, body)
                if reply:
                    send_text(sender, reply)

            executor.submit(_process)

        elif msg_type in ("image", "document", "audio", "video", "sticker"):
            if sender != ADMIN_PHONE:
                executor.submit(send_text, ADMIN_PHONE,
                    f"📎 ميديا من {sender}: {msg_type}\nhttps://wa.me/{sender}"
                )
                executor.submit(send_text, sender,
                    "شكراً خويا! 📸 ما نقدرش نقرا الملفات للأسف.\n"
                    "صيفط رسالة نصية باش نكملو 😊"
                )

        return "ok", 200

    except Exception as e:
        logging.error(f"[WEBHOOK ERROR] {e}", exc_info=True)
        return "ok", 200


@app.route("/test", methods=["POST"])
def test_endpoint():
    """Test: simulate WhatsApp message and send reply"""
    try:
        data    = request.get_json(force=True)
        phone   = "".join(filter(str.isdigit, data.get("phone", ADMIN_PHONE)))
        message = data.get("message", "سلام")

        reply  = handle_logic(phone, message) or ""
        sent   = send_text(phone, reply) if reply else False

        return jsonify({"ok": True, "reply": reply, "sent": sent, "phone": phone})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/catalog-test")
def catalog_test():
    """Send catalog images to admin"""
    phone = request.args.get("phone", ADMIN_PHONE)
    executor.submit(send_catalog_images, phone)
    return jsonify({"ok": True, "sent_to": phone})


@app.route("/state")
def view_state():
    stats = get_stats()
    return jsonify({
        "agent":   "Nessrine v8.0",
        "mongodb": "connected" if get_db() else "file-fallback",
        "stats":   stats
    })

# ============================================================
# KEEP-ALIVE — self-ping every 14 min (prevents Render sleep)
# ============================================================
def _keep_alive():
    time.sleep(90)  # Give gunicorn time to start fully
    while True:
        try:
            r = requests.get(f"{SERVICE_URL}/health", timeout=15)
            logging.info(f"[KEEP-ALIVE] ✅ {r.status_code}")
        except Exception as e:
            logging.warning(f"[KEEP-ALIVE] ⚠️ {e}")
        time.sleep(14 * 60)  # 14 minutes

threading.Thread(target=_keep_alive, daemon=True, name="keep-alive").start()
logging.info("🚀 [BOOT] Keep-alive thread started (ping every 14 min)")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"[BOOT] Nessrine v8.0 — 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
