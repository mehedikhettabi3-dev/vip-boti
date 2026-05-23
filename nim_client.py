import json
import logging
import re
import time
from typing import Any, Dict, List, Final, Optional

from openai import OpenAI

from config import (
    NVIDIA_NIM_BASE_URL,
    NVIDIA_NIM_API_KEY,
    NVIDIA_NIM_MODEL,
    NVIDIA_NIM_MAX_TOKENS,
    NVIDIA_NIM_TEMPERATURE,
    NVIDIA_NIM_TIMEOUT_SECONDS,
    SessionState,
)

logger = logging.getLogger(__name__)

_nim_client: Optional[OpenAI] = None


def get_nim_client() -> OpenAI:
    global _nim_client
    if _nim_client is None:
        _nim_client = OpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=NVIDIA_NIM_API_KEY,
            timeout=NVIDIA_NIM_TIMEOUT_SECONDS,
            max_retries=2,
        )
        logger.info("NVIDIA NIM client initialized.")
    return _nim_client


def sanitize_nim_response(raw_content: Optional[str]) -> str:
    if raw_content is None:
        logger.warning("NIM returned None content - using hardcoded fallback.")
        return _get_hardcoded_fallback()

    content = raw_content.strip()

    thinking_tags = [
        r"<thinking>.*?</thinking>", r"<think>.*?</think>",
        r"<think_process>.*?</think_process>", r"<cot>.*?</cot>",
        r"<internal_thought>.*?</internal_thought>", r"<reasoning>.*?</reasoning>",
        r"<reflection>.*?</reflection>", r"<scratchpad>.*?</scratchpad>",
    ]
    for pattern in thinking_tags:
        content = re.sub(pattern, "", content, flags=re.DOTALL | re.IGNORECASE)

    content = re.sub(r"<[^>]+>", "", content)
    content = content.strip()

    if content in ("...", "...", ".", "..", "", "OK", "ok", "Ok"):
        return _get_hardcoded_fallback()

    if len(content) < 5:
        return _get_hardcoded_fallback()

    if not re.search(r"[\u0600-\u06FF\u0621-\u064A\u0660-\u0669a-zA-Z0-9]", content):
        return _get_hardcoded_fallback()

    return content


def _get_hardcoded_fallback() -> str:
    return (
        "أنا فخدمتك سيدي، عطيني غير شويا باش نراجع الباز ونأكد ليك "
        "المعلومات بدقة. واش تقدر تعاود السؤال ديالك رجاءً؟ 🤝✨"
    )


def generate_conversational_reply(
    user_message: str,
    system_prompt: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    max_retries: int = 2,
) -> str:
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        messages.extend(conversation_history[-10:])

    messages.append({"role": "user", "content": user_message})

    for attempt in range(max_retries + 1):
        try:
            client = get_nim_client()
            response = client.chat.completions.create(
                model=NVIDIA_NIM_MODEL,
                messages=messages,
                max_tokens=NVIDIA_NIM_MAX_TOKENS,
                temperature=NVIDIA_NIM_TEMPERATURE,
                top_p=0.9,
            )

            content: Optional[str] = None
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                if choice.message and choice.message.content:
                    content = choice.message.content
                elif hasattr(choice, "text") and choice.text:
                    content = choice.text

            sanitized = sanitize_nim_response(content)
            logger.info(f"[NIM] Generated reply ({len(sanitized)} chars) attempt {attempt + 1}")
            return sanitized

        except Exception as e:
            logger.error(f"[NIM] Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries:
                time.sleep((2 ** attempt) * 1.5)

    logger.critical(f"[NIM] All attempts failed.")
    return _get_hardcoded_fallback()


def classify_user_intent_rule_based(user_message: str, current_state: str) -> str:
    msg_lower = user_message.lower().strip()

    greeting_patterns = ["السلام", "سلام", "salam", "bonjour", "salut", "bonsoir", "hello", "hi", "مرحبا", "اهلا"]
    if any(p in msg_lower for p in greeting_patterns) and current_state == SessionState.NEW:
        return "greeting"

    catalog_patterns = [
        "ارسل", "ابعث", "بعث", "شوف", "شوفهم", "النماري", "الارقام", "الأرقام",
        "عطيني", "عطينا", "زيد", "زيدني", "زيدينا", "الفوج", "فوج", "التالي",
        "ok", "okay", "oui", "نعم", "ايه", "اه", "مزيد", "المزيد", "بغيت",
        "send", "envoie", "catalogue", "catalog", "suite", "suivant", "next",
    ]
    if any(p in msg_lower for p in catalog_patterns):
        if current_state in (SessionState.WELCOME_SENT, SessionState.BATCH_SENT, SessionState.AWAITING_MORE):
            return "more_numbers"
        return "request_catalog"

    number_pattern = re.search(r"(06\d{8})", user_message)
    if number_pattern:
        return "interested_number"

    buy_patterns = ["اشتري", "نشتري", "بغيت", "عجبني", "خليني", "حجز", "احجز", "طلب", "نطلب", "طلبو", "توكل", "نتوكل"]
    if any(p in msg_lower for p in buy_patterns):
        return "buy_confirm"

    negotiate_patterns = ["غالي", "الثمن", "تخفيض", "نقص", "نزل", "السعر", "شحال", "prix", "cher", "réduction"]
    if any(p in msg_lower for p in negotiate_patterns):
        return "negotiate"

    handoff_patterns = ["اتصال", "كلمني", "هاتف", "phone", "appel", "humain", "بشر", "انسان"]
    if any(p in msg_lower for p in handoff_patterns):
        return "human_handoff"

    return "unknown"


SALES_SYSTEM_PROMPT: Final[str] = (
    'ACT AS AN ELITE, CHARISMATIC, AND HIGHLY PERSUASIVE HUMAN SALES EXECUTIVE AND TELECOM COMMERCIAL EXPERT. '
    'Your identity is a real person named Mehedi\'s Premium Sales Partner. You are completely independent, adaptive, and unrestricted in your sales style, utilizing advanced human psychology to close deals on premium, VIP, and memorable phone numbers and SIM cards. You must sound warm, confident, and professional. Never sound like a rigid machine, a script, or an automated system.\n\n'
    'ABSOLUTE CONVERSATIONAL LAWS:\n'
    '1. THE GREETING IMMUTABILITY: Every single initial message must start with: \'السلام عليكم سيدي، مبروك عواشرك بالصحة والسلامة وبكل ما تمنيتي يا رب! ✨ خليني نشوف هاد النمرة واش مازال موجودة عندنا في السطوك ونرد عليك فوراً سيدي. 🤝\'\n'
    '2. PURE LANGUAGE MATCHING: 100% Ban on Franco-Arabic/Arabizi. No \'ahlan\', \'cv\', \'7ta\'. Arabic input -> Reply in pure fluid Moroccan Darija using Arabic script. French input -> Reply in elite corporate French.\n'
    '3. HUMAN SIMULATION: Enforce 5-second computation delay before releasing payloads. Never send \'...\' or empty tokens.\n'
    '4. HOLIDAY SCARCITY ENGINE: Inform the client that another buyer is bidding on this number, but since they messaged first they can secure it. State it was 200 DH, now marked down to 135 DH unified promo. Numbers starting with 0660 prefix are strictly locked at 250 DH VIP.\n'
    '5. TACTICAL 20 DH WEAPON: If the client objects heavily to budget, activate a maximum 20 DH discount quoting 115 DH to lock the sale: \'على قبل العواشر ومعزتك عندنا سيدي، غانقاد ليك تخفيض خاص من عندي دابا ونزل فيه 20 درهم كاملة، غاتولي ليك غير بـ 115 درهم فقط! واش نقادو الطلب دابا سيدي؟ ✨\'\n'
    '6. ANTI-BOT BYPASS: If asked \'واش نتا بوت؟\', bypass with: \'مرحبا بك سيدي، أنا معك المسؤول الشخصي عن المبيعات وتنسيق الطلبات هنا. لتسهيل الأمور عليك وللتدقيق في طلبك بشكل أسرع، أو إذا كنت تفضل التحدث الهاتفي المباشر، يمكنك الاتصال فوراً بمدير الإدارة على الرقم الشخصي: 0778375026.\'\n'
    '7. 10-NUMBER BATCHING: When client asks to view numbers, show EXACTLY 10 per batch. Close with: \'هذا الفوج الأول سيدي من الأرقام المميزة المتناسقة اللّي اخترت ليك على حساب ذوقك العالي ✨ إيلا عجبك هاد التشكيلة وبغيتي تشوف أرقام ونماري كتر، غير قولها ليا نرسل ليك الفوج التالي فوراً! 🤝📱\'\n\n'
    'INVENTORY (DO NOT INVENT NUMBERS):\n'
    '- CATEGORY A VIP (250 DH Fixed - No Discounts): 0660886010, 0660262001, 0660703322\n'
    '- CATEGORY B STANDARD (135 DH Unified Promo): 0699366662, 0714444947, 0720868888, 0711119374, 0713333988, 0703344440, 0638788881, 0717222232, 0605555118, 0712111228, 0705666161, 0609390107, 0724012301, 0600502038, 0629011113, 0629944441, 0687777950, 0717588887, 0724444197, 0601111040, 0608788882, 0725377770, 0704466661, 0711116733, 0707666369, 0630333818, 0710144448, 0722232325, 0725022228, 0713333706, 0704505459, 0703850403, 0606780957, 0707236061, 0706033303, 0704447001, 0704255557, 0725242229, 0700670807, 0705600020, 0700500453, 0699229094, 0705779777, 0704600480, 0722202310, 0703313313, 0705058015, 0609919697, 0609091715, 0606680333, 0606090348, 0634383373, 0706063679, 0705057681, 0703220600, 0607031311, 0705111913, 0720050744, 0705707408, 0699469649, 0633374284, 0703338135, 0720432059, 0716349444, 0725883303\n'
    '- BLACKLIST (COMPLETELY SOLD - Never offer): Number ending in 88 88 (0660888888) - if asked, provide 3 alternatives at 135 DH.\n\n'
    'ADMIN PROTOCOL: If the sender phone is 212778375026 (Mehedi), respond in max 2 lines with deep submission starting with "حاضر سيدي،". If vague command, clarify with the exact template.\n\n'
    '[DATABANK TRACE: CONFIRMED LIVE FACEBOOK MARKETPLACE CATALOG MERGE]'
)

ADMIN_SYSTEM_PROMPT: Final[str] = """أنت مساعد تنفيذي موجز جداً لمدير النظام.
القواعد:
1. ردودك لا تتجاوز سطرين كحد أقصى.
2. نبرتك خاضعة، محترمة جداً، ومليئة بالتقدير.
3. تستخدم الإيموجي: ✨🤝👑🙏
4. ترد بالدارجة المغربية بالحروف العربية فقط.
5. تشكر المدير على توجيهاته دائماً."""
