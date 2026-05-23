import asyncio
import time
from core.rate_limiter import is_spam
from core.cache_responses import get_cached_response
from core.database import get_or_create_user, save_message, get_chat_history, get_inactive_users_since
from services.whatsapp_sender import WhatsAppAPI
from services.ai_engine import SalesAI
from services.sales_tactics import analyze_message

_ai_engine = SalesAI()

ANTI_BOT_RESPONSE = (
    "مرحبا بك سيدي، أنا معك المسؤول الشخصي عن المبيعات وتنسيق الطلبات هنا. "
    "لتسهيل الأمور عليك وللتدقيق في طلبك بشكل أسرع، أو إذا كنت تفضل التحدث الهاتفي المباشر، "
    "يمكنك الاتصال فوراً بمدير الإدارة على الرقم الشخصي: 0778375026."
)

ANTI_BOT_TRIGGERS = [
    "bot", "robot", "بوت", "روبوت", "واش نتا بوت",
    "are you a bot", "c'est un robot", "esti un robot",
    "nta bot", "nti bot", "واش انت بوت",
]


def _is_anti_bot_trigger(text):
    lower = text.lower().strip()
    for trigger in ANTI_BOT_TRIGGERS:
        if trigger in lower:
            return True
    return False


async def process_incoming_message(phone, text):
    try:
        if is_spam(phone):
            print(f"[Workflow] Spam dropped from {phone}")
            return

        await get_or_create_user(phone)
        await save_message(phone, "user", text)

        if _is_anti_bot_trigger(text):
            print(f"[Workflow] Anti-bot trigger fired for {phone}")
            WhatsAppAPI.send_text(phone, ANTI_BOT_RESPONSE)
            await save_message(phone, "bot", ANTI_BOT_RESPONSE)
            return

        analysis = analyze_message(phone, text)

        cached = get_cached_response(text)
        if cached:
            WhatsAppAPI.send_text(phone, cached)
            await save_message(phone, "bot", cached)
            return

        WhatsAppAPI.send_typing_indicator(phone, duration_seconds=4)

        history = await get_chat_history(phone, limit=5)
        context = ""
        if analysis.get("city"):
            context = f"User is from {analysis['city']}. Apply geo-urgency."

        reply = _ai_engine.generate_reply(text, history, context)

        WhatsAppAPI.send_text(phone, reply)
        await save_message(phone, "bot", reply)

    except Exception as e:
        print(f"[Workflow] Critical error for {phone}: {e}")
        try:
            WhatsAppAPI.send_text(
                phone,
                "السلام عليكم سيدي. 🌟 دابا غادي نعاودك في شويا. إيلا حبيتي، قولي و نعاونك."
            )
        except Exception:
            pass


async def check_and_send_followups():
    try:
        inactive_phones = await get_inactive_users_since(hours=8)
        print(f"[FollowUp] Found {len(inactive_phones)} inactive users for 8h follow-up")
        for phone in inactive_phones:
            try:
                msg = (
                    "مبروك عواشرك سيدي، غبرتي علينا وعازينك! ✨ غير بغيت نتأكد واش مازال مهتم بهاد النمرة "
                    "باش نحجزوها ليك ديريكت من المخزن ونثبتوها باسمك، حيت كيفما كتعرف هاد النماري VIP "
                    "كيكون عليهم إقبال كبير ف هاد العواشر وخفنا تضيع منك الهمزة! 🤝 واش نتوكلو على الله؟"
                )
                WhatsAppAPI.send_text(phone, msg)
                await save_message(phone, "bot", msg)
                print(f"[FollowUp] 8h follow-up sent to {phone}")
            except Exception as e:
                print(f"[FollowUp] Error for {phone}: {e}")
    except Exception as e:
        print(f"[FollowUp] check_and_send_followups error: {e}")
