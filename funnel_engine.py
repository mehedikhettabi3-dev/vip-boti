import asyncio
import re
from typing import Dict, Final, List, Optional, Tuple

_inventory_lock = asyncio.Lock()

CATEGORY_A_VIP: Final[Dict[str, int]] = {
    "0660886010": 250,
    "0660262001": 250,
    "0660703322": 250,
}

CATEGORY_B_STANDARD: Final[Dict[str, int]] = {
    "0699366662": 135, "0714444947": 135, "0720868888": 135,
    "0711119374": 135, "0713333988": 135, "0703344440": 135,
    "0638788881": 135, "0717222232": 135, "0605555118": 135,
    "0712111228": 135, "0705666161": 135, "0609390107": 135,
    "0724012301": 135, "0600502038": 135, "0629011113": 135,
    "0629944441": 135, "0687777950": 135, "0717588887": 135,
    "0724444197": 135, "0601111040": 135, "0608788882": 135,
    "0725377770": 135, "0704466661": 135, "0711116733": 135,
    "0707666369": 135, "0630333818": 135, "0710144448": 135,
    "0722232325": 135, "0725022228": 135, "0713333706": 135,
    "0704505459": 135, "0703850403": 135, "0606780957": 135,
    "0707236061": 135, "0706033303": 135, "0704447001": 135,
    "0704255557": 135, "0725242229": 135, "0700670807": 135,
    "0705600020": 135, "0700500453": 135, "0699229094": 135,
    "0705779777": 135, "0704600480": 135, "0722202310": 135,
    "0703313313": 135, "0705058015": 135, "0609919697": 135,
    "0609091715": 135, "0606680333": 135, "0606090348": 135,
    "0634383373": 135, "0706063679": 135, "0705057681": 135,
    "0703220600": 135, "0607031311": 135, "0705111913": 135,
    "0720050744": 135, "0705707408": 135, "0699469649": 135,
    "0633374284": 135, "0703338135": 135, "0720432059": 135,
    "0716349444": 135, "0725883303": 135,
}

SOLD_NUMBERS: Final[List[str]] = ["0720868888"]

FULL_INVENTORY: Dict[str, int] = {**CATEGORY_A_VIP, **CATEGORY_B_STANDARD}
for s in SOLD_NUMBERS:
    FULL_INVENTORY.pop(s, None)

INVENTORY_ORDER: List[str] = list(FULL_INVENTORY.keys())


async def rebuild_inventory_order(removed_number: Optional[str] = None):
    async with _inventory_lock:
        global INVENTORY_ORDER
        if removed_number:
            FULL_INVENTORY.pop(removed_number, None)
        INVENTORY_ORDER.clear()
        INVENTORY_ORDER.extend(FULL_INVENTORY.keys())


VIP_PRICE: Final[int] = 250
STANDARD_PRICE: Final[int] = 135
MAX_DISCOUNT: Final[int] = 20
DISCOUNTED_PRICE: Final[int] = STANDARD_PRICE - MAX_DISCOUNT
BATCH_SIZE: Final[int] = 10


def format_number_visually(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 10:
        return raw
    prefix = digits[:2] if digits.startswith("06") else digits[:3]
    body = digits[len(prefix):]
    repeat_match = re.search(r"(\d)\1{3}", body)
    if repeat_match:
        start, end = repeat_match.start(), repeat_match.end()
        before = body[:start]
        repeat_block = repeat_match.group()
        after = body[end:]
        parts = []
        if before:
            parts.append(_pair_split(before))
        parts.append(repeat_block)
        if after:
            parts.append(_pair_split(after))
        return f"{prefix} {' '.join(parts)}"
    else:
        return f"{prefix} {_pair_split(body)}"


def _pair_split(seq: str) -> str:
    return " ".join(seq[i:i+2] for i in range(0, len(seq), 2))


def get_batch(cursor: int) -> Tuple[List[str], int, bool]:
    total = len(INVENTORY_ORDER)
    if cursor >= total:
        cursor = 0
    end = min(cursor + BATCH_SIZE, total)
    batch = INVENTORY_ORDER[cursor:end]
    has_more = end < total
    return batch, cursor, has_more


def format_batch_message(batch: List[str]) -> str:
    lines = ["✨ *الأرقام المميزة المتناسقة بمناسبة العواشر* ✨\n"]
    for i, num in enumerate(batch, 1):
        formatted = format_number_visually(num)
        price = FULL_INVENTORY.get(num, STANDARD_PRICE)
        cat = "💎 VIP" if num in CATEGORY_A_VIP else "⭐"
        lines.append(f"{i:02d}. `{formatted}` -> *{price} DH* {cat}")
    lines.append("")
    lines.append(
        "هذا الفوج سيدي من الأرقام المميزة المتناسقة اللّي اخترت ليك على حساب ذوقك العالي ✨ "
        "إيلا عجبك هاد التشكيلة وبغيتي تشوف أرقام ونماري كتر، غير قولها ليا نرسل ليك الفوج التالي فوراً! 🤝📱"
    )
    return "\n".join(lines)


def get_number_price(phone: str) -> int:
    clean = re.sub(r"[^0-9]", "", phone)
    if clean in CATEGORY_A_VIP:
        return VIP_PRICE
    if clean in CATEGORY_B_STANDARD:
        return STANDARD_PRICE
    return -1


def is_number_sold(phone: str) -> bool:
    clean = re.sub(r"[^0-9]", "", phone)
    return clean in SOLD_NUMBERS or clean not in FULL_INVENTORY


def get_alternatives(requested: str, count: int = 3) -> List[str]:
    clean = re.sub(r"[^0-9]", "", requested) if requested else ""
    prefix = clean[:3] if len(clean) >= 3 else "06"
    alts = []
    for num in INVENTORY_ORDER:
        if num.startswith(prefix) and num != clean:
            alts.append(num)
            if len(alts) >= count:
                break
    for num in INVENTORY_ORDER:
        if num not in alts and num != clean:
            alts.append(num)
            if len(alts) >= count:
                break
    return alts[:count]


def apply_discount(original_price: int) -> int:
    return DISCOUNTED_PRICE if original_price == STANDARD_PRICE else VIP_PRICE


CROSS_SELL_HEADER = (
    "يا سيدي مبروك عواشرك أولاً، هاد النمرة صراحة راها عاد تباعت ومازال ما خرجنا حيدناها من السيستيم بالكامل. 😔 "
    "ولكن على قبل ذوقك العالي، خليني نجيب لك أقرب 3 نماري ليها ف الجمالية والسيميتري دابا وموجودين ف السطوك بـ 135 درهم فقط!"
)

HANDOFF_CONFIRMATION = (
    "مبروك عواشرك سيدي، الطلب ديالك ترفع بنجاح! 🚀 واحد الاتصال غايجيك ف الدقائق أو الساعات القادمة من الإدارة "
    "غير للتأكد من جدية الطلب وباش نحيدو النمرة نهائياً من السيستيم ونعطيوك التركيب فابور تال الدار. شكراً لثقتك! 🤝✨"
)

RETENTION_FOLLOWUP = (
    "مبروك عواشرك سيدي، غبرتي علينا وعازينك! ✨ غير بغيت نتأكد واش مازال مهتم بهاد النمرة باش نحجزوها ليك ديريكت من المخزن "
    "ونثبتوها باسمك، حيت كيفما كتعرف هاد النماري VIP كيكون عليهم إقبال كبير ف هاد العواشر وخفنا تضيع منك الهمزة! 🤝 واش نتوكلو على الله؟"
)


def package_admin_notification(
    client_phone: str,
    client_name: Optional[str],
    client_city: Optional[str],
    requested_number: Optional[str],
    final_price: Optional[int],
) -> str:
    return (
        "🚨 [LIVE TRACKING]\n"
        f"📱 نمرة الكليان: +{client_phone}\n"
        f"👤 الاسم الكامل: {client_name or 'غير متوفر'}\n"
        f"📍 المدينة: {client_city or 'غير متوفر'}\n"
        f"💎 النمرة المطلوبة: {requested_number or 'غير محددة'}\n"
        f"💵 الثمن النهائي: {final_price or 0} DH\n"
        "⚡ الحالة: العميل بانتظار مكالمة التأكيد الفورية للطلب."
    )
