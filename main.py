import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from config import (
    WHATSAPP_VERIFY_TOKEN,
    ADMIN_PHONE,
    WHATSAPP_API_URL,
    WHATSAPP_ACCESS_TOKEN,
    MONGO_URI,
    MONGO_DB_NAME,
)
from funnel_engine import (
    INVENTORY_ORDER, BATCH_SIZE,
    get_batch, format_batch_message,
    get_number_price, is_number_sold, get_alternatives,
    apply_discount, package_admin_notification,
    HANDOFF_CONFIRMATION, RETENTION_FOLLOWUP, CROSS_SELL_HEADER,
    format_number_visually, VIP_PRICE, STANDARD_PRICE, DISCOUNTED_PRICE,
    rebuild_inventory_order,
)
from nim_client import (
    generate_conversational_reply,
    sanitize_nim_response,
    SALES_SYSTEM_PROMPT_BASE,
    ADMIN_SYSTEM_PROMPT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

load_dotenv()

CRITICAL_ENV = [
    "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_VERIFY_TOKEN",
    "MONGO_URI", "ADMIN_PHONE", "NVIDIA_NIM_API_KEY"
]
missing = [v for v in CRITICAL_ENV if not os.getenv(v)]
if missing:
    logger.critical("Missing critical env vars: %s. Aborting startup.", missing)
    raise SystemExit(1)

app = FastAPI(title="WhatsApp VIP Sales Bot")
client_http: Optional[httpx.AsyncClient] = None
mongo_client: Optional[AsyncIOMotorClient] = None
db = None


async def ensure_indexes():
    try:
        col = db.client_sessions
        await col.create_index("client_phone", unique=True)
        await col.create_index("state")
        await col.create_index("silence_started_at")
        await col.create_index("is_purchased")
        logger.info("MongoDB indexes verified.")
    except Exception as e:
        logger.warning("Index creation issue: %s", e)


async def get_db():
    global db
    if db is None:
        if mongo_client is None:
            raise RuntimeError("mongo_client is None")
        db = mongo_client[MONGO_DB_NAME]
    return db


send_limiter = asyncio.Semaphore(8)
cached_llm_responses: dict[str, tuple[str, float]] = {}
_cache_llm_ttl = 3600.0
_pending_cleanup: Optional[asyncio.Task] = None


def _register_cleanup_task():
    pass


def _get_message_text(body: dict) -> str:
    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages", [])
        if not messages:
            return ""
        msg = messages[0]
        msg_type = msg.get("type", "")
        if msg_type == "text":
            return msg["text"]["body"].strip()
        elif msg_type == "interactive" and "button_reply" in msg.get("interactive", {}):
            return msg["interactive"]["button_reply"]["title"].strip()
        return ""
    except (KeyError, IndexError, TypeError):
        return ""


def _get_sender_info(body: dict) -> tuple:
    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages", [])
        if not messages:
            return "", ""
        msg = messages[0]
        phone = msg.get("from", "").strip()
        name = value.get("contacts", [{}])[0].get("profile", {}).get("name", phone)
        return phone, name
    except (KeyError, IndexError, TypeError):
        return "", ""


async def send_whatsapp(phone: str, message: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message},
    }
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    async with send_limiter:
        try:
            resp = await client_http.post(
                WHATSAPP_API_URL, json=payload, headers=headers, timeout=10.0
            )
            resp.raise_for_status()
            logger.info("Message sent to %s (len=%d)", phone, len(message))
        except httpx.HTTPStatusError as e:
            logger.error("WhatsApp API error to %s: %s", phone, e.response.text[:300])
        except httpx.RequestError as e:
            logger.error("Network error sending to %s: %s", phone, e)


async def cached_llm_reply(
    prompt: str, system_prompt: str = SALES_SYSTEM_PROMPT_BASE
) -> str:
    cache_key = hashlib.sha256(f"{system_prompt[-100:]}|{prompt[-200:]}".encode()).hexdigest()
    now = datetime.now(timezone.utc).timestamp()
    cached = cached_llm_responses.get(cache_key)
    if cached:
        content, ts = cached
        if now - ts < _cache_llm_ttl:
            logger.info("LLM cache HIT for key=%s", cache_key[:8])
            return content
        del cached_llm_responses[cache_key]
    try:
        reply = await generate_conversational_reply(prompt, system_prompt)
    except Exception as e:
        logger.warning("LLM fallback on error: %s", e)
        reply = "شكراً سيدي، طلبك وصل ونحن نتابعه مع الإدارة فوراً ✅"
    sanitized = sanitize_nim_response(reply)
    cached_llm_responses[cache_key] = (sanitized, now)
    _evict_stale_cache()
    return sanitized


def _evict_stale_cache():
    if len(cached_llm_responses) < 500:
        return
    now = datetime.now(timezone.utc).timestamp()
    stale = [k for k, (_, ts) in cached_llm_responses.items() if now - ts > _cache_llm_ttl]
    for k in stale:
        del cached_llm_responses[k]
    logger.info("Evicted %d stale cache entries", len(stale))


async def get_or_create_session(phone: str, name: str) -> dict:
    db = await get_db()
    now = datetime.now(timezone.utc)
    session = await db.client_sessions.find_one({"client_phone": phone})
    if session:
        return session
    session_data = {
        "client_phone": phone,
        "client_name": name,
        "client_city": None,
        "requested_number": None,
        "batch_cursor": 0,
        "state": "NEW",
        "follow_up_sent": False,
        "is_purchased": False,
        "silence_started_at": now,
        "last_interaction": now,
        "conversation_history": [],
        "created_at": now,
    }
    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$setOnInsert": session_data},
        upsert=True,
    )
    return session_data


async def process_incoming(phone: str, name: str, msg: str):
    db = await get_db()
    session = await get_or_create_session(phone, name)
    state = session.get("state", "NEW")
    last_state_change = session.get("last_state_change")
    now = datetime.now(timezone.utc)

    if state == "PURCHASED":
        await handle_post_purchase(phone, msg)
        return
    elif state in ("HANDOFF_COMPLETE", "CLOSED"):
        await handle_closed(phone, msg)
        return

    if session.get("is_purchased"):
        await handle_post_purchase(phone, msg)
        return

    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$set": {"last_interaction": now, "silence_started_at": now, "follow_up_sent": False}},
    )

    intent = _classify_intent(state, msg, phone)
    logger.info("Phone=%s, state=%s, intent=%s", phone, state, intent)

    if intent == "admin_cmd":
        await handle_admin_command(phone, msg)
        return
    elif intent == "request_number":
        await handle_number_request(phone, msg, session)
        return
    elif intent in ("ask_price", "price_info", "discount_ask"):
        await handle_price_inquiry(phone, msg)
        return
    elif intent == "cross_sell_demand":
        requested = session.get("requested_number")
        alts = get_alternatives(requested) if requested else []
        if alts:
            alt_batch = format_batch_message(alts[:BATCH_SIZE])
            await send_whatsapp(phone, alt_batch)
        else:
            fallback_batch, _, _ = get_batch(0)
            await send_whatsapp(phone, format_batch_message(fallback_batch[:BATCH_SIZE]))
        return
    elif intent == "proceed_purchase":
        await handle_purchase_flow(phone, msg, session)
        return
    elif intent == "new_numbers":
        cursor = session.get("batch_cursor", 0)
        batch, cursor_new, has_more = get_batch(cursor)
        await db.client_sessions.update_one(
            {"client_phone": phone},
            {"$set": {"state": "BATCH_SENT", "batch_cursor": cursor_new, "last_state_change": now}},
        )
        if batch:
            await send_whatsapp(phone, format_batch_message(batch))
        else:
            await send_whatsapp(phone, "عذراً سيدي، لقد استنفذنا كل الأرقام المتاحة حالياً 😔")
        if not has_more:
            await send_whatsapp(phone, "لقد وصلت إلى نهاية القائمة سيدي، هل أعادك من البداية؟ 😊")
        return
    elif intent in ("restart_batches", "repeat_batch"):
        batch, cursor_new, _ = get_batch(0)
        await db.client_sessions.update_one(
            {"client_phone": phone},
            {"$set": {"state": "BATCH_SENT", "batch_cursor": cursor_new, "last_state_change": now}},
        )
        if batch:
            await send_whatsapp(phone, format_batch_message(batch[:BATCH_SIZE]))
        return
    elif intent in ("welcome_greet", "greet_ramadan", "salaam_aleykum"):
        await handle_new(phone, name, session)
        return
    elif intent == "collect_name":
        await db.client_sessions.update_one(
            {"client_phone": phone},
            {"$set": {"client_name": msg, "state": "DATA_COLLECTING_CITY", "last_state_change": now}},
        )
        await send_whatsapp(phone, "شكراً سيدي! الآن، من أي مدينة أنت؟ 🌆")
        return
    elif intent == "collect_city":
        await db.client_sessions.update_one(
            {"client_phone": phone},
            {"$set": {"client_city": msg, "state": "DATA_COLLECTING_CITY", "last_state_change": now}},
        )

    if state in ("DATA_COLLECTING_NAME", "DATA_COLLECTING_CITY"):
        last_change = session.get("last_state_change", now)
        if (now - last_change).total_seconds() > 1800:
            await db.client_sessions.update_one(
                {"client_phone": phone},
                {"$set": {"state": "NEW", "last_state_change": now}},
            )
            await handle_new(phone, name, session)
            return

    if state == "NEW":
        await handle_new(phone, name, session)
    elif state == "BATCH_SENT":
        reply = await cached_llm_reply(msg)
        await send_whatsapp(phone, reply)
    elif state == "PRICE_CONFIRMED":
        await handle_purchase_flow(phone, msg, session)
    else:
        reply = await cached_llm_reply(msg)
        await send_whatsapp(phone, reply)


def _classify_intent(state: str, msg: str, phone: str = "") -> str:
    lower_msg = msg.lower().strip()
    if state == "DATA_COLLECTING_NAME":
        m = re.sub(r"[^أ-يa-zA-Z\s]", "", msg).strip()
        if len(m) >= 2 and not re.search(r"\d", m):
            return "collect_name"
        return "unknown"
    if state == "DATA_COLLECTING_CITY":
        m = re.sub(r"[^أ-يa-zA-Z\s]", "", msg).strip()
        if len(m) >= 2 and not re.search(r"\d", m):
            return "collect_city"
        return "unknown"

    if phone == ADMIN_PHONE:
        if re.search(
            r"(حاضر|نعم|تم|افهم|ok|clear|شوف|عطني|أظهر|اعرض|ارسل|احذف|ديليت|delete|بيع|sold|mark)",
            lower_msg,
        ):
            return "admin_cmd"

    if re.search(
        r"(بغيت نمرة|بيعلي|عطيني رقم|واش كاين|شنو عندك|نمرة|رقم|ديرلي|اريد رقم|وريني|أظهرلي|شوف ليا|عطيني رقم)"
        r"(وأنا جاهز|جيبهالي|ديما شريت|شريت من قبل|عندي زبون|عاود جيب|بغيت نشري)",
        lower_msg,
    ):
        return "request_number"
    if re.search(
        r"(السعر|الثمن|الثمن|التمن|قداش|قداه|شحال|بكم|كم سعر|سعر|بغيت السعر|شنو الثمن|الثمن ديال)"
        r"(عندك رخيص|تخفيض|تخفض|عندك حوايج رخيصة|عندك أرخص|خصم|عندك برومو|برومو|العواشر)",
        lower_msg,
    ):
        return "ask_price"
    if re.search(r"(discount|خصم|تخفيض|عندك تخفيض|برومو|بريس برومو|شحال بعد التخفيض)", lower_msg):
        return "discount_ask"
    if re.search(
        r"(زid|زيدني|عاود جيب|كاين غير هاد|عندك غير هاد|هاد非|هادو|بغيت شي حاجة|بديل|واش كاين شي حاجة)"
        r"(أخرى|آخر|بديل|اختيار|خيارات أخرى|بغيت نبدل|ماعجبنيش|ماعجبتنيش|ما عجبنيش|ما عجبتنيش|واه غير هاد)",
        lower_msg,
    ):
        return "cross_sell_demand"
    if re.search(
        r"(شرا|شريت|بغيت نشري|ديرلي حساب|أنا جاهز|جاهز|جيبه|جيبهالي|ديما|شريت من قبل)"
        r"(خلص|خلصت|حولت|واصل|تم الشراء|تم الطلب|خدم|خدملي|دابا|توا|دابا نشري|دابا نخلص)",
        lower_msg,
    ):
        return "proceed_purchase"
    if re.search(r"(جديد|كاين جديد|عندك جديد|وريني جديد|جيب جديد|كاين نماري جداد)", lower_msg):
        return "new_numbers"
    if re.search(r"(عاود|من الأول|من البداية|ارسل الفوج الأول|الفوج الأول)", lower_msg):
        return "restart_batches"
    if re.search(r"(سلام|السلام عليكم|سلام عليكم|صباح الخير|مساء الخير|مرحبا|أهلا|هاي|هلا|hello|hi|bonjour)", lower_msg):
        return "welcome_greet"
    if re.search(
        r"(عواشر|مبارك|رمضان|رمضان مبارك|عواشر مباركة|الله ينور|يقبل)", lower_msg
    ):
        return "greet_ramadan"
    return "general_chat"


async def handle_new(phone: str, name: str, session: dict):
    db = await get_db()
    now = datetime.now(timezone.utc)
    cursor = session.get("batch_cursor", 0)
    batch, cursor_new, has_more = get_batch(cursor)
    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$set": {"state": "BATCH_SENT", "batch_cursor": cursor_new, "last_state_change": now}},
    )
    welcome = (
        "🎉 السلام عليكم ورحمة الله سيدي! 🤝✨\n\n"
        "بركات عواشر رمضان المباركة! 🌙 الله يتقبل منا ومنكم صالح الأعمال.\n\n"
        "حابس نعرض عليكم مجموعة حصرية من الأرقام المميزة المتناسقة "
        "(نوع VIP ☆☆☆☆☆) بالمناسبة ديال العواشر المباركة! 📱💎\n\n"
        "هاد الأرقام معمولين خصيصاً باش يكونو ساهلة فالحفظ والتكرار، "
        "وزيد عليهم إمكانية تقسيط الثمن على 3 شهور، 3 شهور فقط ماكاينش ! 💳✨\n\n"
        "هاد هو الفوج الأول لي اخترناه ليك حسب ذوقك الرفيع:\n"
    )
    await send_whatsapp(phone, welcome)
    if batch:
        await send_whatsapp(phone, format_batch_message(batch))
    if not batch:
        await send_whatsapp(
            phone,
            "⚠️ للأسف، لا تتوفر أرقام متاحة حالياً. لكن تفضل سيدي نعرض ليك أقرب البدائل:\n"
            + format_batch_message(get_alternatives("", 5)),
        )


async def handle_purchase_flow(phone: str, msg: str, session: dict):
    db = await get_db()
    now = datetime.now(timezone.utc)
    requested = session.get("requested_number")
    price = session.get("last_price") or (get_number_price(requested) if requested else STANDARD_PRICE)
    if not requested:
        await send_whatsapp(
            phone,
            "سيدي، ما زلت ما حددتيش النمرة المطلوبة. أرسل لي الرقم لي بغيتي باش نكملو الطلب 😊",
        )
        return
    if is_number_sold(requested):
        alts = get_alternatives(requested)
        if alts:
            await send_whatsapp(phone, CROSS_SELL_HEADER)
            await send_whatsapp(phone, format_batch_message(alts[:BATCH_SIZE]))
        return
    sale_text = (
        f"✅ تم تسجيل طلبك سيدي!\n"
        f"📱 النمرة: {format_number_visually(requested)}\n"
        f"💵 الثمن: *{price} DH*\n"
        f"💰 بعد التخفيض (إن أمكن): {apply_discount(price)} DH\n\n"
        "سيتم التواصل معك من طرف الإدارة في أقرب وقت لتأكيد الطلب وتفعيله.\n\n"
        "شكراً لثقتك سيدي! 🤝✨"
    )
    await send_whatsapp(phone, HANDOFF_CONFIRMATION)
    await send_whatsapp(phone, sale_text)
    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$set": {"state": "HANDOFF", "last_state_change": now, "is_purchased": True}},
    )
    admin_msg = package_admin_notification(
        phone,
        session.get("client_name"),
        session.get("client_city"),
        requested,
        price,
    )
    await send_whatsapp(ADMIN_PHONE, admin_msg)


async def handle_price_inquiry(phone: str, msg: str):
    reply = (
        "🌟 *أسعار الأرقام المميزة* 🌟\n\n"
        f"💎 *VIP*: {VIP_PRICE} DH فقط\n"
        f"⭐ *قياسي*: {STANDARD_PRICE} DH فقط\n"
        f"💰 *بعد التخفيض (العواشر)*: {DISCOUNTED_PRICE} DH للقياسي\n\n"
        "وإمكانية التقسيط على 3 شهور متاحة لجميع الأرقام! 💳✨"
    )
    await send_whatsapp(phone, reply)


async def handle_number_request(phone: str, msg: str, session: dict):
    db = await get_db()
    now = datetime.now(timezone.utc)
    requested = _extract_number(msg)
    if requested:
        alt = _normalize_phone(requested)
        if alt:
            requested = alt
    if requested and not is_number_sold(requested):
        price = get_number_price(requested)
        formatted = format_number_visually(requested)
        await db.client_sessions.update_one(
            {"client_phone": phone},
            {
                "$set": {
                    "requested_number": requested,
                    "last_price": price,
                    "state": "PRICE_CONFIRMED",
                    "last_state_change": now,
                }
            },
        )
        price_msg = (
            f"✨ النمرة: `{formatted}`\n"
            f"💵 الثمن: *{price} DH*\n"
            f"💰 مع تخفيض العواشر: {apply_discount(price)} DH\n\n"
            "واش توافق على هاد الثمن سيدي؟ 😊\n"
            "رد بـ \"نعم\" أو \"ماشي\" أو \"بغيت نشري\" باش نكملو الطلب!"
        )
        await send_whatsapp(phone, price_msg)
    else:
        alts = get_alternatives(requested if requested else "", 3)
        if alts:
            await send_whatsapp(phone, CROSS_SELL_HEADER)
            await send_whatsapp(phone, format_batch_message(alts[:BATCH_SIZE]))
        else:
            batch, cursor_new, _ = get_batch(0)
            await send_whatsapp(phone, format_batch_message(batch[:BATCH_SIZE]))


def _extract_number(text: str) -> Optional[str]:
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 10:
        return digits[-10:]
    return None


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"[^0-9]", "", raw)
    if len(digits) == 10:
        return digits
    elif len(digits) == 12 and digits.startswith("212"):
        return digits[3:]
    elif len(digits) == 11 and digits.startswith("0"):
        return digits
    return digits if len(digits) >= 10 else ""


async def handle_admin_command(phone: str, msg: str):
    if phone != ADMIN_PHONE:
        return
    lower = msg.lower().strip()
    reply = ""

    if re.search(r"(حاضر|نعم|تم|ok|clear|افهم)", lower):
        reply = "✅ حاضر سيدي، أمرك طاعة. أنا في الخدمة دائمًا 👑"

    elif re.search(r"(شوف|عطني|أظهر|اعرض|ارسل)", lower):
        batch, _, _ = get_batch(0)
        if batch:
            reply = format_batch_message(batch[:BATCH_SIZE])
        else:
            reply = "لا توجد أرقام في المخزون حالياً سيدي."

    elif re.search(r"(احذف|ديليت|delete)", lower):
        num = _extract_number(msg)
        if num:
            await rebuild_inventory_order(num)
            reply = f"✅ تم حذف {num} من السيستيم بنجاح سيدي."
        else:
            reply = "سيدي، ما لقيتش رقم صحيح فهاد الأمر. دير الرقم بوضوح من بعد الأمر."

    elif re.search(r"(بيع|sold|mark)", lower):
        num = _extract_number(msg)
        if num:
            await send_whatsapp(ADMIN_PHONE, f"✅ تم تعليم {num} كمباع سيدي. السيستيم ديالنا تيق بتاع.")
            return
        else:
            reply = "سيدي، ما لقيتش رقم فهاد الأمر."

    else:
        reply = await cached_llm_reply(msg, ADMIN_SYSTEM_PROMPT)

    if reply:
        await send_whatsapp(phone, reply)


async def handle_post_purchase(phone: str, msg: str):
    reply = await cached_llm_reply(
        msg,
        (
            "العميل قام بالشراء بالفعل. كن مهذبا وذكره أنه تم بالفعل. لا تعرض أي أرقام جديدة. "
            "إذا ألح على الشراء، أخبره أن الإدارة ستتواصل معه قريباً. بالدارجة."
        ),
    )
    await send_whatsapp(phone, reply)


async def handle_closed(phone: str, msg: str):
    reply = await cached_llm_reply(
        msg,
        (
            "هذا العميل مغلق نهائياً أو تم تسليمه. لا تقدم أي معلومات أو عروض. "
            "إذا ألح، أخبره أن محادثته انتهت وشكره. بالدارجة المغربية."
        ),
    )
    await send_whatsapp(phone, reply)


async def handle_handoff(phone: str, msg: str, session: dict):
    db = await get_db()
    now = datetime.now(timezone.utc)
    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$set": {"state": "HANDOFF_COMPLETE", "last_state_change": now}},
    )
    await send_whatsapp(
        phone,
        "✅ سيدي، تم تحويل طلبك للإدارة بنجاح. سيتم الاتصال بك قريباً لتأكيد الطلب. 🤝✨",
    )


async def retention_loop():
    while True:
        try:
            await asyncio.sleep(300)
            db = await get_db()
            now = datetime.now(timezone.utc)
            cutoff = now.timestamp() - 79200
            cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
            eligible = await db.client_sessions.find_one_and_update(
                {
                    "silence_started_at": {"$lte": cutoff_dt},
                    "follow_up_sent": False,
                    "is_purchased": {"$ne": True},
                    "state": {"$nin": ["NEW", "HANDOFF_COMPLETE", "CLOSED"]},
                },
                {"$set": {"follow_up_sent": True, "last_retention": now}},
                sort=[("silence_started_at", 1)],
            )
            if eligible:
                phone = eligible.get("client_phone")
                if phone:
                    logger.info("Sending retention follow-up to %s", phone)
                    await send_whatsapp(phone, RETENTION_FOLLOWUP)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Retention loop error: %s", e)


@app.on_event("startup")
async def startup():
    global client_http, mongo_client
    client_http = httpx.AsyncClient(timeout=15.0)
    logger.info("HTTPX client initialized.")
    mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await mongo_client.admin.command("ping")
        logger.info("MongoDB connection OK.")
    except Exception as e:
        logger.critical("MongoDB connection failed: %s", e)
        raise
    await get_db()
    await ensure_indexes()
    asyncio.create_task(retention_loop())
    logger.info("Startup complete: retention loop active.")


@app.on_event("shutdown")
async def shutdown():
    global client_http, mongo_client
    if client_http:
        await client_http.aclose()
    if mongo_client:
        mongo_client.close()
    logger.info("Shutdown complete.")


@app.get("/")
async def root():
    return {"status": "online", "service": "WhatsApp VIP Sales Bot", "version": "4.2"}


@app.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = None,
    hub_verify_token: Optional[str] = None,
    hub_challenge: Optional[str] = None,
):
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return int(hub_challenge) if hub_challenge else 200
    logger.warning("Webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    phone, name = _get_sender_info(body)
    msg = _get_message_text(body)
    if not phone or not msg:
        return {"status": "ignored"}
    logger.info("Incoming from %s (%s): %.80s", phone, name, msg)
    asyncio.create_task(process_incoming(phone, name, msg))
    return {"status": "ok"}
