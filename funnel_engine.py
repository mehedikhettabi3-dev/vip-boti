import logging
import re
from typing import Dict, Final, List, Optional, Tuple

from config import (
    INVENTORY_ORDERED_LIST,
    BATCH_SIZE,
    FULL_INVENTORY,
    CATEGORY_A_VIP,
    STANDARD_PRICE,
    VIP_PRICE,
    MAX_DISCOUNT,
    DISCOUNTED_PRICE,
    SOLD_NUMBERS,
    BATCH_CLOSER_TEXT,
    CROSS_SELL_TEXT,
)

logger = logging.getLogger(__name__)


def format_number_visually(raw_number: str) -> str:
    cleaned = re.sub(r"[^0-9]", "", raw_number)
    if len(cleaned) != 10:
        return raw_number

    prefix = cleaned[:2]
    body = cleaned[2:]

    repeat_match = re.search(r"(\d)\1{3}", body)
    if repeat_match:
        repeat_start = repeat_match.start()
        repeat_end = repeat_match.end()
        repeat_block = repeat_match.group()
        before = body[:repeat_start]
        after = body[repeat_end:]
        parts = []
        if before:
            parts.append(_pair_split(before))
        parts.append(repeat_block)
        if after:
            parts.append(_pair_split(after))
        return f"{prefix} {' '.join(parts)}"
    else:
        return f"{prefix} {_pair_split(body)}"


def _pair_split(digits: str) -> str:
    pairs = [digits[i:i+2] for i in range(0, len(digits), 2)]
    return " ".join(pairs)


def get_batch(cursor: int) -> Tuple[List[str], int, bool]:
    total = len(INVENTORY_ORDERED_LIST)
    if cursor >= total:
        cursor = 0
    end_index = min(cursor + BATCH_SIZE, total)
    batch = INVENTORY_ORDERED_LIST[cursor:end_index]
    has_more = end_index < total
    return batch, cursor, has_more


def format_batch_message(batch: List[str]) -> str:
    lines: List[str] = []
    lines.append("✨ *الأرقام المميزة المتناسقة* ✨\n")
    for i, number in enumerate(batch, start=1):
        formatted = format_number_visually(number)
        price = FULL_INVENTORY.get(number, STANDARD_PRICE)
        category = "💎 VIP" if number in CATEGORY_A_VIP else "⭐"
        lines.append(f"{i:02d}. `{formatted}` -> *{price} DH* {category}")
    lines.append("")
    lines.append(BATCH_CLOSER_TEXT)
    return "\n".join(lines)


def get_number_price(phone_number: str) -> int:
    cleaned = re.sub(r"[^0-9]", "", phone_number)
    if cleaned in CATEGORY_A_VIP:
        return VIP_PRICE
    if cleaned in FULL_INVENTORY:
        return STANDARD_PRICE
    return -1


def is_number_sold(phone_number: str) -> bool:
    cleaned = re.sub(r"[^0-9]", "", phone_number)
    return cleaned in SOLD_NUMBERS or cleaned not in FULL_INVENTORY


def get_alternative_numbers(requested_number: str, count: int = 3) -> List[str]:
    cleaned = re.sub(r"[^0-9]", "", requested_number)
    prefix = cleaned[:4] if len(cleaned) >= 4 else cleaned[:3]
    alternatives: List[str] = []
    for num in INVENTORY_ORDERED_LIST:
        if num.startswith(prefix) and num != cleaned:
            alternatives.append(num)
            if len(alternatives) >= count:
                break
    if len(alternatives) < count:
        for num in INVENTORY_ORDERED_LIST:
            if num not in alternatives and num != cleaned:
                alternatives.append(num)
                if len(alternatives) >= count:
                    break
    return alternatives[:count]


def apply_discount(original_price: int) -> int:
    if original_price == VIP_PRICE:
        return VIP_PRICE
    return max(DISCOUNTED_PRICE, original_price - MAX_DISCOUNT)


def format_discount_message(original_price: int, discounted_price: int) -> str:
    discount_amount = original_price - discounted_price
    return (
        f"على قبل العواشر ومعزتك عندنا سيدي، غانقاد ليك تخفيض خاص "
        f"من عندي دابا ونزل فيه {discount_amount} درهم كاملة، "
        f"غاتولي ليك غير بـ {discounted_price} درهم فقط! "
        f"واش نقادو الطلب دابا سيدي؟ ✨"
    )


def generate_cross_sell_response(requested_number: str) -> str:
    alternatives = get_alternative_numbers(requested_number)
    formatted_alts = [format_number_visually(alt) for alt in alternatives]
    alt_list = "\n".join([f"  . `{f}` -> 135 DH ⭐" for f in formatted_alts])
    return f"{CROSS_SELL_TEXT}\n\n{alt_list}\n\nواش كيعجبوك شي واحد فيهم سيدي؟ 🤝"


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
        f"💵 الثمن النهائي: {final_price or 'غير محدد'} DH\n"
        "⚡ الحالة: العميل بانتظار مكالمة التأكيد الفورية للطلب."
    )
