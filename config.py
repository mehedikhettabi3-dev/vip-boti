import os
from dotenv import load_dotenv
from typing import Dict, List, Final

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

WHATSAPP_PHONE_NUMBER_ID: Final[str] = os.getenv("WHATSAPP_PHONE_NUMBER_ID", os.getenv("META_PHONE_ID", ""))
WHATSAPP_ACCESS_TOKEN: Final[str] = os.getenv("WHATSAPP_ACCESS_TOKEN", os.getenv("META_TOKEN", ""))
WHATSAPP_API_VERSION: Final[str] = "v21.0"
WHATSAPP_API_URL: Final[str] = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
WHATSAPP_VERIFY_TOKEN: Final[str] = os.getenv("WHATSAPP_VERIFY_TOKEN", os.getenv("VERIFY_TOKEN", "MehediVip2026"))

MONGO_URI: Final[str] = os.getenv("MONGO_URI", os.getenv("MONGODB_URI", ""))
MONGO_DB_NAME: Final[str] = "vip_numbers_bot"
MONGO_COLL_SESSIONS: Final[str] = "client_sessions"
MONGO_COLL_INVENTORY: Final[str] = "phone_inventory"
MONGO_COLL_LOGS: Final[str] = "system_logs"

NVIDIA_NIM_BASE_URL: Final[str] = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_NIM_API_KEY: Final[str] = os.getenv("NVIDIA_NIM_API_KEY", os.getenv("NVIDIA_API_KEY", ""))
NVIDIA_NIM_MODEL: Final[str] = os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_NIM_MAX_TOKENS: Final[int] = 600
NVIDIA_NIM_TEMPERATURE: Final[float] = 0.3
NVIDIA_NIM_TIMEOUT_SECONDS: Final[int] = 12

ADMIN_PHONE: Final[str] = "212778375026"

CATEGORY_A_VIP: Final[Dict[str, int]] = {
    "0660886010": 250,
    "0660262001": 250,
    "0660703322": 250,
}

CATEGORY_B_STANDARD: Final[Dict[str, int]] = {
    "0699366662": 135, "0714444947": 135, "0720868888": 135, "0711119374": 135, "0713333988": 135,
    "0703344440": 135, "0638788881": 135, "0717222232": 135, "0605555118": 135, "0712111228": 135,
    "0705666161": 135, "0609390107": 135, "0724012301": 135, "0600502038": 135, "0629011113": 135,
    "0629944441": 135, "0687777950": 135, "0717588887": 135, "0724444197": 135, "0601111040": 135,
    "0608788882": 135, "0725377770": 135, "0704466661": 135, "0711116733": 135, "0707666369": 135,
    "0630333818": 135, "0710144448": 135, "0722232325": 135, "0725022228": 135, "0713333706": 135,
    "0704505459": 135, "0703850403": 135, "0606780957": 135, "0707236061": 135, "0706033303": 135,
    "0704447001": 135, "0704255557": 135, "0725242229": 135, "0700670807": 135, "0705600020": 135,
    "0700500453": 135, "0699229094": 135, "0705779777": 135, "0704600480": 135, "0722202310": 135,
    "0703313313": 135, "0705058015": 135, "0609919697": 135, "0609091715": 135, "0606680333": 135,
    "0606090348": 135, "0634383373": 135, "0706063679": 135, "0705057681": 135, "0703220600": 135,
    "0607031311": 135, "0705111913": 135, "0720050744": 135, "0705707408": 135, "0699469649": 135,
    "0633374284": 135, "0703338135": 135, "0720432059": 135, "0716349444": 135, "0725883303": 135,
}

SOLD_NUMBERS: Final[List[str]] = ["0660888888"]

FULL_INVENTORY: Final[Dict[str, int]] = {**CATEGORY_A_VIP, **CATEGORY_B_STANDARD}
for sold_num in SOLD_NUMBERS:
    FULL_INVENTORY.pop(sold_num, None)

INVENTORY_ORDERED_LIST: Final[List[str]] = list(FULL_INVENTORY.keys())

STANDARD_PRICE: Final[int] = 135
VIP_PRICE: Final[int] = 250
MAX_DISCOUNT: Final[int] = 20
DISCOUNTED_PRICE: Final[int] = STANDARD_PRICE - MAX_DISCOUNT

class SessionState:
    NEW: str = "NEW"
    WELCOME_SENT: str = "WELCOME_SENT"
    BATCH_SENT: str = "BATCH_SENT"
    AWAITING_MORE: str = "AWAITING_MORE"
    PRICE_QUOTED: str = "PRICE_QUOTED"
    NEGOTIATING: str = "NEGOTIATING"
    ORDER_CONFIRMED: str = "ORDER_CONFIRMED"
    DATA_COLLECTING_NAME: str = "DATA_COLLECTING_NAME"
    DATA_COLLECTING_CITY: str = "DATA_COLLECTING_CITY"
    HANDOFF_COMPLETE: str = "HANDOFF_COMPLETE"
    SILENT: str = "SILENT"
    CLOSED: str = "CLOSED"

SILENCE_THRESHOLD_HOURS: Final[int] = 2
FOLLOW_UP_DELAY_HOURS: Final[int] = 8
BATCH_SIZE: Final[int] = 10

BATCH_CLOSER_TEXT: Final[str] = (
    "هذا الفوج سيدي من الأرقام المميزة المتناسقة اللّي اخترت ليك "
    "على حساب ذوقك العالي ✨ إيلا عجبك هاد التشكيلة وبغيتي تشوف أرقام "
    "ونماري كتر، غير قولها ليا نرسل ليك الفوج التالي فوراً! 🤝📱"
)

HANDOFF_TEXT_TEMPLATE: Final[str] = (
    "مبروك عواشرك سيدي، الطلب ديالك ترفع بنجاح! 🚀 واحد الاتصال "
    "غايجيك ف الدقائق أو الساعات القادمة من الإدارة غير للتأكد من "
    "جدية الطلب وباش نحيدو النمرة نهائياً من السيستيم ونعطيوك التركيب "
    "فابور تال الدار. شكراً لثقتك! 🤝✨"
)

FOLLOW_UP_TEXT_TEMPLATE: Final[str] = (
    "مبروك عواشرك سيدي، غبرتي علينا وعازينك! ✨ غير بغيت نتأكد واش "
    "مازال مهتم بهاد النمرة باش نحجزوها ليك ديريكت من المخزن ونثبتوها "
    "باسمك، حيت كيفما كتعرف هاد النماري VIP كيكون عليهم إقبال كبير "
    "ف هاد العواشر وخفنا تضيع منك الهمزة! 🤝 واش نتوكلو على الله؟"
)

CROSS_SELL_TEXT: Final[str] = (
    "يا سيدي مبروك عواشرك أولاً، هاد النمرة صراحة راها عاد تباعت "
    "ومازال ما خرجنا حيدناها من السيستيم بالكامل. 😔 ولكن على قبل "
    "ذوقك العالي، خليني نجيب لك أقرب 3 نماري ليها ف الجمالية والسيميتري "
    "دابا وموجودين ف السطوك بـ 135 درهم فقط!"
)

ADMIN_CLARIFY_TEXT: Final[str] = (
    "حاضر سيدي، أمرك مطاع فوراً ولكن لم أستوعب بدقة أي رقم أو عميل "
    "تقصد سيدي لكي لا أرتكب أي خطأ في النظام. هل تقصد الرقم [X] "
    "أم العميل [Y]؟ تفضل بأمرك سيدي وسأفذه في الحين. ✨🤝"
)

WELCOME_TEXT: Final[str] = (
    "السلام عليكم سيدي، مرحبا بيك عند أفضل مزود نماري VIP فالمغرب! ✨📱 "
    "خليني نشوف ليك هاد النمرة واش موجودة فالباز ديالنا..."
)
