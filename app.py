"""
PROJECT SNIPER v7.0 — VIP Numbers Morocco WhatsApp Bot
Hybrid Architecture: Strict 4-Step State Machine + MEGA-DICTIONARY + NVIDIA RAG
"""
import os, sys, re, json, logging, threading, random, requests
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()
try:
    if sys.stdout.encoding != 'utf-8': sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8': sys.stderr.reconfigure(encoding='utf-8')
except: pass

# ============================================================
# CONFIG
# ============================================================
WHATSAPP_TOKEN    = os.environ.get("ACCESS_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "vip_bot_2026")
ADMIN_PHONE       = os.environ.get("ADMIN_PHONE", "212625489153")
NVIDIA_API_KEY    = os.environ.get("NVIDIA_API_KEY", "")
CATALOG_URL       = os.environ.get("CATALOG_URL", "https://vip-boti.onrender.com").rstrip("/")
META_API_URL      = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"

# VIP pricing (NO 200 DH — strict business rule)
PRICES = {"100": "100 DH", "135": "135 DH", "150": "150 DH"}
VIP_PREFIXES = ["061", "0661", "0662", "0668", "070", "072"]

# ============================================================
# LOGGING
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_log_path = os.path.join(BASE_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(_log_path, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
    ]
)

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=5)
_lock = threading.Lock()
processed_ids = set()
user_states = {}

# ============================================================
# VIP MEGA DICTIONARY — Moroccan Darija Intent Detection
# ============================================================
VIP_MEGA_DICTIONARY = {
    "demand_intent": re.compile(
        r'\b(bgh?it|bghiti|bghina|brit|b4it|bght|khasni|khassni|kn9lb|n9lb|bari|baghi|'
        r'bghit\s*nechri|nir\s*brit|andi\s*gharad|mohim\s*brit|'
        r'sift|sft|3tini|3etini|a3tini|'
        r'بغيت|بغيتي|بغينا|باغي|بريت|بغت|خصني|كنقلب|محوج|محتاج|'
        r'بغيت\s*نشري|غير\s*بريت|عندي\s*غرض|المهم\s*بريت|اريد|'
        r'صيفط|سيفط|عطيني|اعطيني|نشري)\b', re.I
    ),
    "availability": re.compile(
        r'\b(wach\s*k[ai]yn?|wach\s*kine|wach\s*3end[kc]om|k[ai]yn?\s*chi|b9at\s*chi|dispo|'
        r'واش\s*كاين|واش\s*متوفر|واش\s*عندكم|كاين\s*شي|كاينة\s*شي|عندكم|بقات)\b', re.I
    ),
    "catalog": re.compile(
        r'\b(nmra|nmera|nemra|nwamer|nwamar|nwamr|nmari|ra9m|r9m|'
        r'numero|numéro|numéros|number|numbers|nimer|nimiro|'
        r'رقم|نمرة|نوامر|نيميرو|'
        r'أرقام|ارقام|كتالوج|catalog|catalogue|warini|وريني)\b', re.I
    ),
    "budget_pricing": re.compile(
        r'\b(chhal|bchhal|bch7al|bch7l|ch7l|thaman|taman|prix|price|ثمن|شحال|بشحال|'
        r'bo\s*100|bo\s*135|bo\s*150|ب\s*100|ب\s*135|ب\s*150|'
        r'100\s*dh|135\s*dh|150\s*dh|كلسي|katklsi)\b', re.I
    ),
    "operator": re.compile(
        r'\b(iam|maroc\s*telecom|ittissalat|itisalat|orange|méditel|meditel|inwi|wana|reseau|'
        r'ina\s*reseau|achmn\s*reseau|'
        r'اتصالات|اتصالات\s*المغرب|اورانج|اورنج|انوي|ريزو|الشبكة|المشغل|اشمن\s*ريزو)\b', re.I
    ),
    "registration": re.compile(
        r'\b(smiti|smit|smia|ismi|ism|kifach\s*tsjel|kifach\s*doz|contrat|la\s*carte|'
        r'carte\s*bancaire|activation|'
        r'سميتي|بسميتي|سمية|الاسم|اسمي|كيفاش\s*تسجل|كونطرا|عقد|تسجيل|تفعيل)\b', re.I
    ),
    "delivery": re.compile(
        r'\b(tawsil|livraison|kifach\s*tawsil|kifach\s*nkhls|kifach\s*ntwasel|nkhls|'
        r'توصيل|كيفاش\s*التوصيل|التوصيل|الخلاص|الكاش|المانة|فين\s*نوصل)\b', re.I
    ),
    "greeting": re.compile(
        r'\b(salam|slm|ahlan|ahlan|slaaaam|مرحبا|السلام|سلام|أهلا|اهلا|bonjour|salut|hi|hello|hey)\b', re.I
    ),
    "thanks": re.compile(
        r'\b(shukran|choukran|merci|mrc|thanks|شكرا)\b', re.I
    ),
    "cancel": re.compile(
        r'\b(l[ai]|non|no|mabghitch|mabghitx|إلغاء|لا|مابغيتش|خلاص|stop|cancel|annuler)\b', re.I
    ),
    "trust": re.compile(
        r'\b(garantie|garantir|sérieux|sérieuse|legit|serious|ثقة|مضمون)\b', re.I
    ),
    "bargain": re.compile(
        r'\b(ghali|rkhis|r5is|na9s|tna9so|discount|تخفيض|غالي|رخيص|نقص|تنقصو)\b', re.I
    )
}

# ============================================================
# HELPERS
# ============================================================
def digits_only(s):
    return "".join(filter(str.isdigit, str(s or "")))

def normalize_phone(raw):
    d = digits_only(raw)
    if d.startswith("212"): return d
    if d.startswith("0") and len(d) >= 10: return "212" + d[1:]
    if len(d) == 9: return "212" + d
    return d

def extract_moroccan_number(text):
    # Clean: remove Arabizi digits used as letters (3=ع, 7=ح, 9=ق, 5=خ, etc.)
    # Strategy: find viable phone patterns via regex scanning, not global digits_only
    # Pattern: optional +212/00212/0 + [5-7] + 8 more digits (spaces/dashes allowed everywhere)
    m = re.search(r'(?:\+?212|00212|0)([\s.\-/]*[5-7][\s.\-/]*\d[\s.\-/]*\d[\s.\-/]*\d[\s.\-/]*\d[\s.\-/]*\d[\s.\-/]*\d[\s.\-/]*\d[\s.\-/]*\d)', text)
    if m:
        raw = m.group(0)
        d = digits_only(raw)
        if d.startswith("212") and len(d) >= 12: return "0" + d[3:13]
        if d.startswith("0") and len(d) >= 10: return d[:10]
    # Fallback: try extracting 10 consecutive digits starting with 0
    d = digits_only(text)
    idx = d.find("0")
    if idx >= 0 and len(d) >= idx + 10:
        candidate = d[idx:idx+10]
        if candidate.startswith("0") and len(candidate) == 10:
            return candidate
    return None

def is_vip_number(num):
    for p in VIP_PREFIXES:
        if num.startswith(p): return True
    return False

def send_whatsapp(to, text):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        logging.error("[SEND] Missing credentials")
        return False
    try:
        r = requests.post(
            META_API_URL,
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:4096]}},
            timeout=15
        )
        ok = r.status_code in (200, 201)
        if not ok: logging.error(f"[SEND FAIL] {r.status_code} {r.text[:200]}")
        return ok
    except Exception as e:
        logging.error(f"[SEND ERROR] {e}")
        return False

def send_whatsapp_async(to, text):
    executor.submit(send_whatsapp, to, text)

def save_order(order):
    fpath = os.path.join(BASE_DIR, "orders.json")
    with _lock:
        orders = []
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f: orders = json.load(f)
            except: orders = []
        orders.append(order)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=4)

# ============================================================
# INTENT DETECTION
# ============================================================
def detect_intent(text):
    t = text.strip()
    results = []
    for category, pattern in VIP_MEGA_DICTIONARY.items():
        if pattern.search(t):
            results.append(category)
    return results

# ============================================================
# STATIC RESPONSES
# ============================================================
def response_welcome():
    return ("👑 مرحبا بيك فـ *VIP Numbers Morocco*!\n\n"
            "عندنا أرقام VIP مغربية فاخرة:\n"
            "📱 Maroc Telecom | Inwi | Orange\n\n"
            "🔹 *100 DH*\n🔹 *135 DH*\n🔹 *150 DH*\n\n"
            "عطيني *سميتك* باش نبداو! 🖊️")

def response_catalog():
    return ("📋 *كتالوج أرقام VIP:*\n\n"
            "🔹 *100 DH* — أرقام مميزة\n"
            "🔹 *135 DH* — أرقام VIP\n"
            "🔹 *150 DH* — أرقام SUPER VIP\n\n"
            "الدفع عند الاستلام ✅\n"
            "التوصيل لجميع المدن 🇲🇦\n\n"
            "صيفط ليا النمرة اللي عجباتك! 🚀")

def response_pricing():
    return ("💰 *أسعار أرقام VIP:*\n\n"
            "🔹 *100 DH*\n🔹 *135 DH*\n🔹 *150 DH*\n\n"
            "الدفع عند الاستلام 🚚\n"
            "نوصل لجميع مدن المغرب 🇲🇦")

def response_help():
    return ("❓ *كيفاش نخدم؟*\n\n"
            "1️⃣ صيفط *نوامر* — كتالوج\n"
            "2️⃣ صيفط *شحال* — الأثمنة\n"
            "3️⃣ صيفط النمرة — حجز مباشر\n"
            "4️⃣ صيفط *سلام* — تحية\n"
            "5️⃣ صيفط *لا* — إلغاء\n\n"
            "أي سؤال آخر؟ أنا هنا 💬")

def response_operators():
    return ("عندنا أرقام VIP من جميع المشغلين المغاربة:\n"
            "📶 *Maroc Telecom* — 061, 0661\n"
            "📶 *Inwi* — 070, 072\n"
            "📶 *Orange* — 0662, 0668\n\n"
            "بغيتي تشوف النوامر؟ صيفط *نوامر*")

def response_registration():
    return ("التسجيل ساهل خويا! 😊\n"
            "• كتسجل النمرة بسميتك فـ أقرب وكالة\n"
            "• الخلاص عند الاستلام ✅\n"
            "• الملكية كتكون ديالك 100% 🔥\n\n"
            "بغيتي تبدأ؟ صيفط النمرة اللي بغيتي 🚀")

def response_delivery():
    return ("التوصيل ساهل خويا! 📦\n"
            "• كنوصلو لجميع المدن المغربية 🇲🇦\n"
            "• الخلاص عند الاستلام ✅\n"
            "• ما كتخلص حتى تشد النمرة فيدك 💪\n"
            "• نقبلو الكاش عند الاستلام فقط 💵\n\n"
            "بغيتي تطلب؟ صيفط النمرة 🚀")

def response_trust():
    return ("✅ *VIP Numbers Morocco* — خدمة موثوقة وثقة منذ سنوات!\n\n"
            "• الخلاص عند الاستلام — ما كتخلص حتى تشد النمرة 🤝\n"
            "• النمرة كتكون ديالك 100% بعد التسجيل 🔥\n"
            "• عندنا بزاف ديال الكليانات راضيين والحمدلله 🙏\n\n"
            "إذا باقي عندك شك، جرب نمرة وحدة أولاً! صيفط النمرة اللي بغيتي 🚀")

def response_bargain():
    return ("خويا الأثمنة ديالنا راه مزيانين بزاف! 😊\n\n"
            "🔹 *100 DH*\n🔹 *135 DH*\n🔹 *150 DH*\n\n"
            "هاد النوامر عند اتصالات ولا أورنج كتخلص عليها فاكتورة كل شهر — "
            "أما هنا مرة وحدة وتبقى ديالك العمر كامل! 💪🔥\n\n"
            "بغيتي تشوف النوامر؟ صيفط *نوامر*")

def response_order_complete(data, order_id):
    return (f"✅ *تم تأكيد الطلب!* 🎉\n\n"
            f"📱 النمرة: {data.get('vip_number', '')}\n"
            f"👤 الاسم: {data.get('name', '')}\n"
            f"📍 المدينة: {data.get('city', '')}\n"
            f"📞 الهاتف: {data.get('contact_phone', '')}\n"
            f"🆔 الطلب: {order_id}\n\n"
            "غنتصلو بيك قريبا باش نأكدو التوصيل 🤝\n"
            "شكرا على ثقتك خويا! 👑")

def build_admin_alert(sender, data, order_id):
    return ("🚨 *طلب VIP جديد — Project Sniper*\n"
            f"📱 الرقم: {data.get('vip_number', 'غير محدد')}\n"
            f"👤 الاسم: {data.get('name', '')}\n"
            f"📍 المدينة: {data.get('city', '')}\n"
            f"📞 هاتف: {data.get('contact_phone', '')}\n"
            f"🆔 الطلب: {order_id}\n"
            f"📲 تواصل: https://wa.me/{sender}")

# ============================================================
# NVIDIA RAG FALLBACK
# ============================================================
def ask_nvidia(question):
    if not NVIDIA_API_KEY: return None
    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "meta/llama-3.3-70b-instruct",
                "messages": [
                    {"role": "system", "content": (
                        "أنت مساعد مبيعات مغربي محترف لمتجر 'VIP Numbers Morocco'. "
                        "تتحدث بالدارجة المغربية. تبيع أرقام هواتف VIP (Maroc Telecom, Inwi, Orange). "
                        "الأسعار: 100 DH، 135 DH، 150 DH فقط. الدفع عند الاستلام. "
                        "أجب عن أسئلة العملاء العامة فقط. إذا طلب الشراء، قل له صيفط النمرة."
                    )},
                    {"role": "user", "content": question}
                ],
                "temperature": 0.5,
                "max_tokens": 256
            },
            timeout=20
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        logging.warning(f"[NVIDIA] Status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logging.error(f"[NVIDIA] {e}")
    return None

# ============================================================
# STRICT 4-STEP LEAD CAPTURE STATE MACHINE
# ============================================================
# Step 0: User sends target VIP number  →  Ask name
# Step 1: User sends name              →  Ask city
# Step 2: User sends city              →  Ask phone
# Step 3: User sends phone             →  SAVE ORDER + IMMEDIATE ADMIN ALERT via Meta API

def run_state_machine(sender, text):
    state = user_states.get(sender)
    if not state:
        return None

    step = state.get("step", 0)
    data = state.get("data", {})

    # ── INTERRUPTION HANDLER: check for cancel/help/greeting during ANY step ──
    t_stripped = text.strip()
    if not t_stripped:
        prompts = ["", "المرجو إدخال رقم VIP صحيح 📱", "المرجو إدخال الاسم 📝", "المرجو إدخال المدينة 📍", "المرجو إدخال رقم الهاتف 📞"]
        return prompts[step] if step < len(prompts) else prompts[0]

    t_lower = t_stripped.lower()

    # Step 3 special: "لا" / "non" / "no" = no phone, NOT cancel
    words = t_lower.strip().split()
    if step == 3 and words and words[0] in ["لا", "non", "no", "ma3ndich", "ma3ndi", "ma3endich", "ma3endi"]:
        data["contact_phone"] = "لا يوجد"
        order_id = f"SNIPER-{datetime.now().strftime('%d%m%Y-%H%M%S')}-{random.randint(100,999)}"
        order = {
            "id": order_id, "sender": sender,
            "vip_number": data.get("vip_number", ""),
            "customer": {"name": data.get("name", ""), "city": data.get("city", ""), "phone": "لا يوجد"},
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "pending"
        }
        save_order(order)
        alert = build_admin_alert(sender, data, order_id)
        send_whatsapp(ADMIN_PHONE, alert)
        user_states.pop(sender, None)
        return response_order_complete(data, order_id)

    # General cancel (but not single "لا" in step 3)
    if re.search(r'\b(l[ai]|non|no|إلغاء|مابغيتش|خلاص|stop|cancel|annuler)\b', t_lower, re.I):
        user_states.pop(sender, None)
        return "واخا، تم إلغاء الطلب. إلا بغيتي شي حاجة أخرى، أنا هنا 😊"
    if re.search(r'\b(مساعدة|help|aide|كيفاش)\b', t_lower, re.I):
        return response_help()
    if re.search(r'\b(salam|slm|سلام|مرحبا|hi|hello|bonjour)\b', t_lower, re.I):
        return response_welcome()

    # During step 0: catalog/pricing queries show info but keep state
    if step == 0:
        intents = detect_intent(t_stripped)
        if "catalog" in intents:
            return response_catalog()
        if "budget_pricing" in intents:
            return response_pricing()

    if step == 0:
        num = extract_moroccan_number(t_stripped)
        if not num or not is_vip_number(num):
            return "⚠️ هاد الرقم ما هوش صحيح! صيفط رقم VIP مغربي صحيح (مثال: 0612345678) 📱"
        data["vip_number"] = num
        user_states[sender] = {"step": 1, "data": data}
        return "ما هو اسمك الكريم؟ 🖊️"

    if step == 1:
        data["name"] = t_stripped
        user_states[sender] = {"step": 2, "data": data}
        return f"شكرا خويا {data['name']}! 😊\nفي أي مدينة ساكن؟ 📍"

    if step == 2:
        data["city"] = t_stripped
        user_states[sender] = {"step": 3, "data": data}
        return "آخر حاجة — رقم هاتفك للتواصل (أو صيفط *لا* إلا ما عندكش) 📞"

    if step == 3:
        phone = t_stripped
        if phone.lower() in ["لا", "non", "no", "ma3ndich", "ma3ndi", "ma3endich", "ma3endi"]:
            phone = "لا يوجد"
        data["contact_phone"] = phone

        order_id = f"SNIPER-{datetime.now().strftime('%d%m%Y-%H%M%S')}-{random.randint(100,999)}"
        order = {
            "id": order_id,
            "sender": sender,
            "vip_number": data.get("vip_number", ""),
            "customer": {
                "name": data.get("name", ""),
                "city": data.get("city", ""),
                "phone": data.get("contact_phone", "")
            },
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending"
        }
        save_order(order)

        # IMMEDIATE Meta API POST to admin (synchronous — critical)
        alert = build_admin_alert(sender, data, order_id)
        send_whatsapp(ADMIN_PHONE, alert)

        user_states.pop(sender, None)
        return response_order_complete(data, order_id)

    user_states.pop(sender, None)
    return None

# ============================================================
# MAIN LOGIC
# ============================================================
ERROR_MESSAGE = (
    "⚠️ *النظام مزدحم حالياً* 🤖\n\n"
    "المرجو ترك رسالة في هذا الرقم، فالنظام لا يعمل حالياً بسبب كثرة الرسائل.\n"
    "سيتم الرد عليك في أقرب وقت ممكن.\n\n"
    "⚠️ *Système surchargé* 🤖\n\n"
    "Veuillez laisser un message à ce numéro, le système ne fonctionne pas "
    "actuellement en raison du grand nombre de messages.\n"
    "Nous vous répondrons dès que possible."
)

def handle_logic(sender, text):
    try:
        t = text.strip()
        t_lower = t.lower()

        # ── CHECK ACTIVE STATE MACHINE ──────────────────────────
        if sender in user_states:
            reply = run_state_machine(sender, t)
            if reply: return reply
            # If state machine returns None, fall through

        # ── PRIORITY 1: User sent a phone number directly → START CAPTURE with number
        num = extract_moroccan_number(t)
        if num and is_vip_number(num):
            user_states[sender] = {"step": 1, "data": {"vip_number": num}}
            return f"🎯 النمرة: *{num}*\nما هو اسمك الكريم؟ 🖊️"

        # ── DETECT INTENT FROM MEGA-DICTIONARY ──────────────────
        intents = detect_intent(t)

        # ── ROUTE BY INTENT ─────────────────────────────────────
        # URLs: skip intent routing, just welcome
        if t.startswith("http://") or t.startswith("https://") or t.startswith("www."):
            return response_welcome()

        invalid_prices = re.search(r'\b(200|50|30|20|10)\s*(dh|درهم)\b', t, re.I)

        # If the user asks about a specific operator, show operator info
        if "operator" in intents:
            return response_operators()

        # 1. Explicit buy / demand / number query → START CAPTURE
        if "demand_intent" in intents or "availability" in intents:
            if invalid_prices and not num:
                return ("⚠️ *هاد الثمن غير متوفر!* الأثمنة اللي عندنا:\n\n"
                        "🔹 *100 DH*\n🔹 *135 DH*\n🔹 *150 DH*\n\n"
                        "بغيتي تشوف النوامر المتوفرة؟ صيفط *نوامر* 🚀")
            user_states[sender] = {"step": 0, "data": {}}
            return "🎯 ما هو رقم VIP اللي باغي تدخل عليه؟ 🤝"

        # 3. Registration / activation / payment method question
        if "registration" in intents:
            return response_registration()

        # 5. Catalog request
        if "catalog" in intents:
            return response_catalog()

        # 6. Pricing
        if "budget_pricing" in intents:
            return response_pricing()

        # 7. Delivery / payment question
        if "delivery" in intents:
            return response_delivery()

        # 8. Trust / guarantee question
        if "trust" in intents:
            return response_trust()

        # 9. Bargaining
        if "bargain" in intents:
            return response_bargain()

        # 10. Greeting
        if "greeting" in intents:
            return response_welcome()

        # 11. Thanks
        if "thanks" in intents:
            return "العفو خويا! الله يبارك فيك 😊 ديما فالخدمة 👑"

        # 12. Cancel — clean up state
        if "cancel" in intents:
            user_states.pop(sender, None)
            return "واخا، تم الإلغاء. إلا بغيتي شي حاجة أخرى، أنا هنا 😊"

        # ── NVIDIA RAG FALLBACK (general questions only) ────────
        if NVIDIA_API_KEY:
            answer = ask_nvidia(t)
            if answer: return answer

        return response_welcome()
    except Exception as e:
        logging.error(f"[HANDLE ERROR] sender={sender} text={text!r} error={e}")
        return ERROR_MESSAGE

# ============================================================
# FLASK ROUTES
# ============================================================
@app.route("/")
def home():
    return jsonify({"status": "online", "project": "Project Sniper", "version": "7.0.0"}), 200

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "project": "Project Sniper - VIP Numbers Morocco",
        "version": "7.0.0",
        "active_sessions": len(user_states),
        "nvidia_ready": bool(NVIDIA_API_KEY),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logging.info("[WEBHOOK] Meta verified")
            return challenge, 200
        return "Forbidden", 403

    try:
        data = request.get_json(force=True)
        if not data or "entry" not in data:
            return "ok", 200

        msg = data["entry"][0]["changes"][0]["value"].get("messages", [None])[0]
        if not msg:
            return "ok", 200

        msg_id = msg.get("id", "")
        if msg_id in processed_ids:
            return "ok", 200
        processed_ids.add(msg_id)
        if len(processed_ids) > 2000:
            processed_ids.clear()

        sender = digits_only(msg["from"])

        if msg.get("type") == "text":
            reply = handle_logic(sender, msg["text"]["body"])
            if reply:
                send_whatsapp_async(sender, reply)
        else:
            send_whatsapp_async(sender, "شكرا خويا! صيفط النمرة بالكتابة باش نكملو 😊")

        return "ok", 200

    except Exception as e:
        logging.error(f"[WEBHOOK ERROR] {e}")
        return "ok", 200

@app.route("/test", methods=["POST"])
def test():
    data = request.get_json(force=True)
    phone = data.get("phone", "212638388885")
    message = data.get("message", "سلام")
    reply = handle_logic(phone, message) or ""
    if reply:
        send_whatsapp(phone, reply)
    return jsonify({"ok": True, "reply": reply})

@app.route("/state")
def view_state():
    safe = {}
    for k, v in list(user_states.items())[:20]:
        safe[k[-4:]] = {"step": v.get("step"), "data_keys": list(v.get("data", {}).keys())}
    return jsonify({"count": len(user_states), "states": safe})

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"[BOOT] Project Sniper v7.0 — 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
