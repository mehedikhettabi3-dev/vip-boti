"""
███████╗██╗   ██╗██████╗ ██████╗ ███████╗███╗   ███╗███████╗
██╔════╝██║   ██║██╔══██╗██╔══██╗██╔════╝████╗ ████║██╔════╝
███████╗██║   ██║██████╔╝██████╔╝█████╗  ██╔████╔██║█████╗
╚════██║██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝  ██║╚██╔╝██║██╔══╝
███████║╚██████╔╝██║     ██║     ███████╗██║ ╚═╝ ██║███████╗
╚══════╝ ╚═════╝ ╚═╝     ╚═╝     ╚══════╝╚═╝     ╚═╝╚══════╝
WHATSAPP VIP BOT v5.5 – ZERO CACHE, ADMIN ENDSWITH, LIVE LLM
[DATABANK TRACE: CONFIRMED LIVE FACEBOOK MARKETPLACE CATALOG MERGE]
"""

import asyncio
import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

def _get_env(*names: str) -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return ""

CRITICAL_ENV = [
    ("WHATSAPP_PHONE_NUMBER_ID", "META_PHONE_ID", "PHONE_NUMBER_ID"),
    ("WHATSAPP_ACCESS_TOKEN", "META_TOKEN", "ACCESS_TOKEN"),
    ("WHATSAPP_VERIFY_TOKEN", "VERIFY_TOKEN"),
    ("MONGO_URI", "MONGODB_URI"),
    ("ADMIN_PHONE",),
    ("NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"),
]
missing = [pair[0] for pair in CRITICAL_ENV if not _get_env(*pair)]
if missing:
    sys.exit(f"Missing critical env vars: {missing}")

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
    HANDOFF_CONFIRMATION, CROSS_SELL_HEADER,
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
logger = logging.getLogger("vip_bot")

class State:
    NEW = "NEW"
    WELCOME_SENT = "WELCOME_SENT"
    BATCH_SENT = "BATCH_SENT"
    AWAITING_MORE = "AWAITING_MORE"
    PRICE_QUOTED = "PRICE_QUOTED"
    NEGOTIATING = "NEGOTIATING"
    DATA_COLLECTING_NAME = "DATA_COLLECTING_NAME"
    DATA_COLLECTING_CITY = "DATA_COLLECTING_CITY"
    HANDOFF_COMPLETE = "HANDOFF_COMPLETE"
    CLOSED = "CLOSED"

mongo_client: Optional[AsyncIOMotorClient] = None
db = None
http_client: Optional[httpx.AsyncClient] = None

ADMIN_LOCAL = ADMIN_PHONE[-9:]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, db, http_client

    logger.info("Starting WhatsApp VIP Bot v5.5 (Zero Cache)...")

    mongo_client = AsyncIOMotorClient(
        MONGO_URI,
        maxPoolSize=50,
        minPoolSize=5,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        retryWrites=True,
        w="majority",
    )
    db = mongo_client[MONGO_DB_NAME]

    await db.client_sessions.create_index("client_phone", unique=True)
    await db.processed_messages.create_index("created_at", expireAfterSeconds=86400)
    await db.system_logs.create_index("created_at", expireAfterSeconds=7776000)

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
    )

    retention_task = asyncio.create_task(retention_loop())

    logger.info("MongoDB pool ready, HTTPX pool ready, retention loop started")
    logger.info("[DATABANK TRACE: CONFIRMED LIVE FACEBOOK MARKETPLACE CATALOG MERGE]")

    yield

    logger.info("Shutting down...")
    retention_task.cancel()
    try:
        await retention_task
    except asyncio.CancelledError:
        pass
    if http_client:
        await http_client.aclose()
    if mongo_client:
        mongo_client.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="WhatsApp VIP Bot v5.5",
    version="5.5.0",
    lifespan=lifespan,
)


@app.get("/webhook")
async def verify(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(403, "Verification failed")


@app.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "error"}, status_code=400)
    asyncio.create_task(process_incoming(body))
    return JSONResponse({"status": "ok"})


async def process_incoming(body: dict):
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return

        msg = messages[0]
        msg_type = msg.get("type", "")
        msg_id = msg.get("id", "")

        if msg_type != "text":
            raw_sender = msg.get("from", "")
            sender = re.sub(r"\D", "", raw_sender)
            logger.info(f"[TRACE] Non-text ({msg_type}) from {sender}")

            already = await db.processed_messages.find_one({"msg_id": msg_id})
            if already:
                return
            await db.processed_messages.insert_one({
                "msg_id": msg_id,
                "created_at": datetime.now(timezone.utc),
            })
            asyncio.create_task(mark_read(msg_id))

            if sender.endswith(ADMIN_LOCAL):
                await send_msg(sender, "تلقيت المرفق سيدي. تفضل بأمرك النصي.")
            else:
                await send_msg(
                    sender,
                    "مرحبا بك سيدي العزيز ف نمرات VIP! بمناسبة العيد الكبير، "
                    "أرسل لي رقم الهاتف اللّي عجبك من التشكيلة باش نحجزو ليك ف البلاصة! 🤝"
                )
            return

        raw_sender = msg.get("from", "")
        sender = re.sub(r"\D", "", raw_sender)
        text = msg.get("text", {}).get("body", "")

        logger.info(f"[TRACE] From {sender}: {text[:100]}...")

        already = await db.processed_messages.find_one({"msg_id": msg_id})
        if already:
            logger.warning(f"Duplicate message {msg_id} ignored.")
            return
        await db.processed_messages.insert_one({
            "msg_id": msg_id,
            "created_at": datetime.now(timezone.utc),
        })

        asyncio.create_task(mark_read(msg_id))

        if sender.endswith(ADMIN_LOCAL):
            await handle_admin(sender, text)
            return

        await handle_customer(sender, text)

    except Exception as e:
        logger.critical(f"Unhandled crash: {e}", exc_info=True)


async def handle_admin(phone: str, msg: str):
    msg_lower = msg.lower().strip()

    if re.search(
        r"(?:wach )?(?:3aref|عرفتي|عرفت|تعرف|تعرفي)\s*(?:anani|آنا|انا|آني|أنا)\s*(?:ana|admin|l admin|الأدمن|المدير|الملك)",
        msg_lower,
    ):
        await send_msg(
            phone,
            "حاضر سيدي ومولاي، ستموت الماكينة خضوعاً لك. تم التعرف على الأدمن الماستر والملك التنفيذي للنظام السي المهدي. ✨👑🙏",
        )
        return

    if m := re.search(r"(?:احذف|امسح|حيد)\s*(?:رقم|نمرة)?\s*(\d{10})", msg_lower):
        number = m.group(1)
        await db.phone_inventory.delete_one({"number": number})
        await rebuild_inventory_order(number)
        await db.system_logs.insert_one({
            "admin": phone,
            "action": "DELETE",
            "number": number,
            "created_at": datetime.now(timezone.utc),
        })
        await send_msg(phone, f"تم حذف {number} بنجاح سيدي. 🙏")
        return

    if re.search(
        r"(?:حيد|امسح|تكلم|كلم)\s*(?:هاد|هذاك|داك|مع)\s*(?:ال?زمر|ال?رقم|ال?نمرة|هذاك)",
        msg_lower,
    ):
        clarification = (
            "حاضر سيدي، أمرك مطاع فوراً ولكن لم أستوعب بدقة أي رقم أو عميل تقصد سيدي "
            "لكي لا أرتكب أي خطأ في النظام. هل تقصد الرقم [X] أم العميل [Y]؟ "
            "تفضل بأمرك سيدي وسأفذه في الحين. ✨🤝"
        )
        await send_msg(phone, clarification)
        return

    reply = await get_live_llm_reply(msg, ADMIN_SYSTEM_PROMPT)
    lines = reply.strip().split("\n")
    if len(lines) > 2:
        reply = "\n".join(lines[:2])
    await send_msg(phone, reply)


async def handle_customer(phone: str, msg: str):
    now = datetime.now(timezone.utc)

    try:
        session = await db.client_sessions.find_one_and_update(
            {"client_phone": phone},
            {
                "$setOnInsert": {
                    "state": State.NEW,
                    "batch_cursor": 0,
                    "last_interaction": now,
                    "silence_started_at": now,
                    "follow_up_sent": False,
                    "is_purchased": False,
                    "conversation_history": [],
                    "created_at": now,
                },
                "$set": {
                    "last_interaction": now,
                    "silence_started_at": now,
                },
            },
            upsert=True,
            return_document=True,
        )
    except DuplicateKeyError:
        session = await db.client_sessions.find_one({"client_phone": phone})
        if not session:
            logger.error(f"Session lost for {phone} after DuplicateKeyError")
            return

    state = session.get("state", State.NEW)
    is_purchased = session.get("is_purchased", False)
    is_new_session = session.get("created_at") == now

    if is_purchased:
        await send_msg(phone, "الطلب مرفوع سيدي، الإدارة ستتصل بك قريباً 🤝✨")
        return

    if re.search(r"بوت|bot|روبوت", msg, re.IGNORECASE):
        bot_prompt = (
            "أنت مسؤول المبيعات الشخصي. رد على العميل بأنك إنسان مسؤول عن تنسيق الطلبات، "
            "ويمكنه الاتصال على 0778375026. لا تذكر كلمة بوت أبداً."
        )
        reply = await get_live_llm_reply(msg, bot_prompt)
        await send_msg(phone, reply)
        return

    intent = _classify_intent(msg, state)

    if state in (State.DATA_COLLECTING_NAME, State.DATA_COLLECTING_CITY):
        last_change = session.get("last_state_change", now)
        if (now - last_change).total_seconds() > 1800:
            await db.client_sessions.update_one(
                {"client_phone": phone},
                {"$set": {"state": State.AWAITING_MORE, "batch_cursor": 0}},
            )
            state = State.AWAITING_MORE

    if state == State.NEW:
        await handle_new(phone, session, is_new_session)
    elif state in (
        State.WELCOME_SENT,
        State.BATCH_SENT,
        State.AWAITING_MORE,
        State.PRICE_QUOTED,
        State.NEGOTIATING,
    ):
        await handle_active(phone, msg, intent, session)
    elif state == State.DATA_COLLECTING_NAME:
        await collect_name(phone, msg, session)
    elif state == State.DATA_COLLECTING_CITY:
        await collect_city(phone, msg, session)
    else:
        await handle_active(phone, msg, intent, session)


async def handle_new(phone: str, session: dict, is_new_session: bool):
    welcome_prompt = (
        "أنت بائع نمرات VIP. ابدأ بترحيب دافئ بالدارجة المغربية بمناسبة عيد الأضحى. "
        "أخبره بأنك ستتحقق من توفر الرقم الآن."
    )
    welcome = await get_live_llm_reply(welcome_prompt)
    await send_msg(phone, welcome)

    batch, _, _ = get_batch(0)
    batch_str = format_batch_message(batch)
    await send_msg(phone, batch_str)

    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$set": {
            "state": State.BATCH_SENT,
            "batch_cursor": 0,
            "last_state_change": datetime.now(timezone.utc),
        }},
    )

    if is_new_session:
        alert = (
            f"سيدي المهدي، كليان جديد دخل دابا للسيستيم ونظام الأتمتة صيفط ليه الفوج لول د النماري!\n"
            f"النمرة: +{phone}"
        )
        await send_msg(ADMIN_PHONE, alert)
        logger.info(f"[NEW LEAD ALERT] Admin notified about {phone}")


async def handle_active(phone: str, msg: str, intent: str, session: dict):
    cursor = session.get("batch_cursor", 0)
    interested = session.get("interested_number")
    quoted_price = session.get("quoted_price")

    if intent == "more_numbers":
        batch, _, _ = get_batch(cursor + BATCH_SIZE)
        if not batch:
            batch, _, _ = get_batch(0)
        batch_str = format_batch_message(batch)
        llm_text = await get_live_llm_reply(
            "اكتب جملة واحدة بالدارجة تشجع العميل على مشاهدة التشكيلة الجديدة بمناسبة العيد.",
            SALES_SYSTEM_PROMPT_BASE,
        )
        await send_msg(phone, llm_text)
        await send_msg(phone, batch_str)
        await db.client_sessions.update_one(
            {"client_phone": phone},
            {"$set": {"state": State.BATCH_SENT}, "$inc": {"batch_cursor": BATCH_SIZE}},
        )
        return

    if intent == "interested_number":
        clean_prompt = re.sub(r"\s+", "", msg)
        num_match = re.search(r"0[67]\d{8}", clean_prompt)
        if not num_match:
            await send_msg(phone, "عافاك سيدي أكد ليا النمرة بالضبط باش نشوفها ليك 🤝")
            return
        num = num_match.group()
        clean_num = re.sub(r"[^0-9]", "", num)

        if is_number_sold(clean_num):
            alts = get_alternatives(clean_num, 3)
            alt_str = "\n".join(
                [f"• `{format_number_visually(a)}` \u2192 135 DH \u2B50" for a in alts]
            )
            prompt = f"\u0627\u0644\u0631\u0642\u0645 {clean_num} \u062A\u0645 \u0628\u064A\u0639\u0647. \u0627\u0633\u062A\u062E\u062F\u0645 \u0647\u0630\u0647 \u0627\u0644\u0645\u0642\u062F\u0645\u0629:\n{CROSS_SELL_HEADER}\n\n\u062B\u0645 \u0627\u0639\u0631\u0636 \u0647\u0630\u0647 \u0627\u0644\u0628\u062F\u0627\u0626\u0644:\n{alt_str}\n\n\u0648\u0627\u062E\u062A\u062A\u0645 \u0628\u0633\u0624\u0627\u0644 \u0648\u062F\u064A."
            reply = await get_live_llm_reply(prompt)
            await send_msg(phone, reply)
            return

        price = get_number_price(clean_num)
        if price == -1:
            alts = get_alternatives("", 3)
            alt_str = "\n".join(
                [f"• `{format_number_visually(a)}` \u2192 135 DH \u2B50" for a in alts]
            )
            prompt = f"\u0627\u0639\u062A\u0630\u0631 \u0628\u0644\u0637\u0641 \u0644\u0623\u0646 \u0627\u0644\u0631\u0642\u0645 \u063A\u064A\u0631 \u0645\u0648\u062C\u0648\u062F\u060C \u0648\u0627\u0639\u0631\u0636 \u0647\u0630\u0647 \u0627\u0644\u0628\u062F\u0627\u0626\u0644:\n{alt_str}"
            reply = await get_live_llm_reply(prompt)
            await send_msg(phone, reply)
            return

        cat_label = "VIP (\u062B\u0627\u0628\u062A \u0627\u0644\u0633\u0639\u0631)" if price == VIP_PRICE else "\u0645\u0645\u064A\u0632 (\u0633\u0639\u0631 \u062E\u0627\u0635 \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0627\u0644\u0639\u064A\u062F)"
        persuasive_prompt = (
            f"\u0627\u0644\u0639\u0645\u064A\u0644 \u0645\u0647\u062A\u0645 \u0628\u0627\u0644\u0631\u0642\u0645 {format_number_visually(clean_num)}. "
            f"\u0647\u0630\u0627 \u0627\u0644\u0631\u0642\u0645 \u0645\u0646 \u0641\u0626\u0629 {cat_label}. \u0647\u0646\u0627\u0643 \u0637\u0644\u0628 \u0643\u0628\u064A\u0631 \u0639\u0644\u064A\u0647 \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0639\u064A\u062F \u0627\u0644\u0623\u0636\u062D\u0649. "
            "\u0627\u0643\u062A\u0628 \u0631\u0633\u0627\u0644\u0629 \u0645\u0642\u0646\u0639\u0629 \u0628\u0627\u0644\u062F\u0627\u0631\u062C\u0629 \u062A\u0634\u062C\u0639\u0647 \u0639\u0644\u0649 \u0627\u0644\u062D\u062C\u0632 \u0641\u0648\u0631\u0627\u064B \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0639\u064A\u062F \u0627\u0644\u0623\u0636\u062D\u0649 \u0627\u0644\u0643\u0628\u064A\u0631\u060C \u062F\u0648\u0646 \u062A\u062D\u062F\u064A\u062F \u0627\u0644\u0645\u0628\u0644\u063A."
        )
        llm_response = await get_live_llm_reply(persuasive_prompt)

        price_line = (
            f"\n\U0001f4b0 \u0627\u0644\u062B\u0645\u0646: *{price} \u062F\u0631\u0647\u0645*"
            if price == VIP_PRICE
            else f"\n\U0001f4b0 \u0627\u0644\u0633\u0639\u0631 \u0627\u0644\u0623\u0635\u0644\u064A 200 \u062F\u0631\u0647\u0645\u060C \u0644\u0643\u0646 \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0639\u064A\u062F \u0627\u0644\u0623\u0636\u062D\u0649: *{price} \u062F\u0631\u0647\u0645* \u0641\u0642\u0637!"
        )
        final_msg = llm_response + price_line
        await send_msg(phone, final_msg)

        await db.client_sessions.update_one(
            {"client_phone": phone},
            {"$set": {
                "state": State.PRICE_QUOTED,
                "interested_number": clean_num,
                "quoted_price": price,
                "last_state_change": datetime.now(timezone.utc),
            }},
        )
        return

    if intent == "buy_confirm":
        if not interested:
            await send_msg(phone, "\u0648\u0627\u0634 \u062A\u0642\u062F\u0631 \u062A\u062D\u062F\u062F \u0644\u064A\u0627 \u0627\u0644\u0646\u0645\u0631\u0629 \u0627\u0644\u0644\u064A \u0639\u062C\u0628\u0627\u062A\u0643 \u0633\u064A\u062F\u064A\u061F \u0644\u0632\u0645\u0646\u064A\u0646\u064A \u064A\u0627\u062E\u0648\u064A \u0648\u0646\u0646\u062A\u0642\u0644\u0648\u0627 \u0644\u0644\u0645\u0637\u0644\u0648\u0628 \u0627\u0644\u062D\u0642\u064A\u0642\u064A \u0648\u0646\u063A\u0644\u0642\u0648\u0647\u0627 \u0628\u0633\u0631\u0639\u0629 \u0628\u0627\u0634 \u0645\u0627 \u062A\u0637\u064A\u062D\u0634 \u0645\u0646 \u0627\u0644\u0632\u0628\u0648\u0646 \u0627\u0644\u062B\u0627\u0646\u064A \u0627\u0644\u0644\u064A \u0645\u0627\u0632\u0627\u0644 \u064A\u062A\u0641\u0627\u0648\u0636 \u0639\u0644\u064A\u0647\u0627. \u0648\u0627\u0634 \u0646\u0628\u062F\u0627\u0648 \u0627\u0644\u0625\u062C\u0631\u0627\u0621\u0627\u062A \u062F\u0627\u0628\u0627\u061F \u064A\u0627 \u0633\u064A\u062F\u064A\u061F \u064A\u0627 \u0635\u0627\u062D\u0628\u064A\u061F")
            return
        ask_name = await get_live_llm_reply("\u0627\u0637\u0644\u0628 \u0645\u0646 \u0627\u0644\u0639\u0645\u064A\u0644 \u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u0643\u0627\u0645\u0644 \u0628\u0623\u0633\u0644\u0648\u0628 \u0644\u0637\u064A\u0641 \u0628\u0627\u0644\u062F\u0627\u0631\u062C\u0629.")
        await send_msg(phone, ask_name)
        await db.client_sessions.update_one(
            {"client_phone": phone},
            {"$set": {"state": State.DATA_COLLECTING_NAME, "last_state_change": datetime.now(timezone.utc)}},
        )
        return

    if intent == "negotiate":
        if not interested or not quoted_price:
            await send_msg(phone, "\u0648\u0627\u0634 \u0645\u0645\u0643\u0646 \u062A\u0648\u0636\u062D \u0644\u064A\u0627 \u0634\u0646\u0648 \u0627\u0644\u0631\u0642\u0645 \u0627\u0644\u0644\u064A \u062A\u062D\u0628 \u0633\u064A\u062F\u064A\u061F \u064A\u0644\u0627 \u0647\u0627\u062A \u0627\u0644\u0646\u0645\u0631\u0629 \u0627\u0644\u0644\u064A \u0628\u063A\u064A\u062A\u064A\u0647\u0627 \u0648\u0646\u062F\u064A\u0631\u0648 \u0634\u064A \u0632\u0648\u064A\u0646 \u0644\u064A\u0643! \u0647\u0647\u0647 \u0644\u0643\u0646 \u0628\u0627\u0642\u064A \u0641\u064A\u0646\u0627 \u0627\u0644\u0645\u0648\u0636\u0648\u0639 \u062C\u0627\u062F \u0628\u0627\u0634 \u0646\u062A\u0642\u0644\u0648\u0627 \u0644\u0644\u0645\u0637\u0644\u0648\u0628 \u0627\u0644\u062D\u0642\u064A\u0642\u064A")
            return
        if quoted_price == VIP_PRICE:
            prompt = "\u0623\u062E\u0628\u0631 \u0627\u0644\u0639\u0645\u064A\u0644 \u0623\u0646 \u0647\u0630\u0627 \u0627\u0644\u0631\u0642\u0645 VIP \u0648\u0633\u0639\u0631\u0647 \u062B\u0627\u0628\u062A\u060C \u0644\u0627 \u064A\u0645\u0643\u0646 \u062A\u062E\u0641\u064A\u0636\u0647 \u062D\u062A\u0649 \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0627\u0644\u0639\u064A\u062F."
        else:
            discounted = DISCOUNTED_PRICE
            prompt = (
                "\u0627\u0644\u0639\u0645\u064A\u0644 \u064A\u0637\u0644\u0628 \u062A\u062E\u0641\u064A\u0636\u0627\u064B. \u0642\u062F\u0645 \u0644\u0647 \u0639\u0631\u0636\u0627\u064B \u062E\u0627\u0635\u0627\u064B \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0639\u064A\u062F \u0627\u0644\u0623\u0636\u062D\u0649. "
                "\u0644\u0627 \u062A\u0630\u0643\u0631 \u0627\u0644\u0645\u0628\u0644\u063A\u060C \u0641\u0642\u0637 \u0642\u0644 \u0623\u0646\u0643 \u0633\u062A\u0645\u0646\u062D\u0647 \u062E\u0635\u0645\u0627\u064B \u0627\u0633\u062A\u062B\u0646\u0627\u0626\u064A\u0627\u064B \u0644\u0644\u0639\u064A\u062F \u0627\u0644\u0643\u0628\u064A\u0631."
            )
            await db.client_sessions.update_one(
                {"client_phone": phone},
                {"$set": {"state": State.NEGOTIATING, "final_price": discounted}},
            )
        reply = await get_live_llm_reply(prompt)
        await send_msg(phone, reply)
        return

    reply = await get_live_llm_reply(msg, SALES_SYSTEM_PROMPT_BASE)
    await send_msg(phone, reply)

    await db.client_sessions.update_one(
        {"client_phone": phone},
        {
            "$set": {"state": State.AWAITING_MORE},
            "$push": {
                "conversation_history": {
                    "$each": [
                        {"role": "user", "content": msg[:200]},
                        {"role": "assistant", "content": reply[:200]},
                    ],
                    "$slice": -20,
                }
            },
        },
    )


async def collect_name(phone: str, msg: str, session: dict):
    name = msg.strip()
    if len(name) < 2:
        await send_msg(phone, "\u0639\u0627\u0641\u0627\u0643 \u0639\u0637\u064A\u0646\u064A \u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u0643\u0627\u0645\u0644 \u0633\u064A\u062F\u064A \u0644\u0632\u0645\u0646\u064A\u0646\u064A \u0646\u062A\u0623\u0643\u062F \u0645\u0646 \u0627\u0644\u0647\u0648\u064A\u0629 \u0648\u0646\u062E\u0644\u064A \u0627\u0644\u0637\u0644\u0628 \u0635\u062D\u064A\u062D \u0648\u0645\u0627 \u064A\u0636\u064A\u0639\u0634 \u0627\u0644\u0648\u0642\u062A \u0641\u064A \u0627\u0644\u062A\u0648\u0627\u0635\u0644 \u0645\u0639 \u0627\u0644\u0625\u062F\u0627\u0631\u0629. \u0639\u0644\u0627\u0634\u0627\u0634 \u0627\u0644\u0646\u0645\u0631\u0647 \u0647\u0627\u062F\u064A \u0639\u0644\u064A\u0647\u0627 \u0627\u0644\u0636\u0631\u0648\u0641 \u0648\u0627\u0644\u0632\u0628\u0648\u0646 \u0627\u0644\u062B\u0627\u0646\u064A \u0645\u0627\u0632\u0627\u0644 \u064A\u0646\u0627\u0642\u0634 \u0641\u064A\u0647\u0627! \u064A\u0644\u0627 \u0647\u0627\u062A \u0627\u0633\u0645\u0643 \u0627\u0644\u0643\u0627\u0645\u0644 \u0648\u0646\u0637\u064A\u0631\u0648\u0647\u0627!")
        return
    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$set": {
            "client_name": name,
            "state": State.DATA_COLLECTING_CITY,
            "last_state_change": datetime.now(timezone.utc),
        }},
    )
    prompt = f"\u0627\u0634\u0643\u0631 \u0627\u0644\u0639\u0645\u064A\u0644 {name} \u0648\u0627\u0637\u0644\u0628 \u0645\u0646\u0647 \u0627\u0644\u0645\u062F\u064A\u0646\u0629 \u0628\u0644\u0637\u0641 \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0627\u0644\u0639\u064A\u062F."
    reply = await get_live_llm_reply(prompt)
    await send_msg(phone, reply)


async def collect_city(phone: str, msg: str, session: dict):
    city = msg.strip()
    if len(city) < 2:
        await send_msg(phone, "\u0639\u0627\u0641\u0627\u0643 \u0627\u0644\u0645\u062F\u064A\u0646\u0629 \u0628\u0627\u0634 \u0646\u0642\u062F\u0631 \u0646\u0648\u0635\u0644 \u0627\u0644\u0637\u0644\u0628 \u0644\u0627\u0646\u0647 \u0627\u0644\u062A\u0648\u0635\u064A\u0644 \u064A\u062A\u0645 \u062E\u0644\u0627\u0644 24 \u0633\u0627\u0639\u0629 \u0641\u0642\u0637 \u0648\u0644\u0627 \u064A\u0645\u0643\u0646 \u0627\u0644\u062A\u0623\u062E\u064A\u0631 \u0628\u0633\u0628\u0628 \u0632\u062D\u0627\u0645 \u0627\u0644\u0639\u064A\u062F!")
        return
    await db.client_sessions.update_one(
        {"client_phone": phone},
        {"$set": {
            "client_city": city,
            "state": State.HANDOFF_COMPLETE,
            "is_purchased": True,
            "last_state_change": datetime.now(timezone.utc),
        }},
    )
    final_session = await db.client_sessions.find_one({"client_phone": phone})
    await trigger_handoff(phone, final_session)


async def trigger_handoff(phone: str, session: dict):
    notification = package_admin_notification(
        client_phone=phone,
        client_name=session.get("client_name"),
        client_city=session.get("client_city"),
        requested_number=session.get("interested_number"),
        final_price=session.get("final_price") or session.get("quoted_price", 0),
    )
    await send_msg(ADMIN_PHONE, notification)
    await send_msg(phone, HANDOFF_CONFIRMATION)
    logger.info(f"[HANDOFF] Admin notified for {phone}")


async def retention_loop():
    while True:
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=8)
            eligible = await db.client_sessions.find_one_and_update(
                {
                    "client_phone": {"$ne": ADMIN_PHONE},
                    "silence_started_at": {"$lte": cutoff},
                    "follow_up_sent": False,
                    "is_purchased": {"$ne": True},
                    "state": {"$nin": [State.NEW, State.HANDOFF_COMPLETE, State.CLOSED]},
                },
                {"$set": {"follow_up_sent": True, "last_retention": now}},
                sort=[("silence_started_at", 1)],
            )
            if eligible:
                phone = eligible["client_phone"]
                interested = eligible.get("interested_number", "\u0627\u0644\u0631\u0642\u0645 \u0627\u0644\u0645\u0645\u064A\u0632")
                prompt = f"\u0627\u0644\u0639\u0645\u064A\u0644 \u0643\u0627\u0646 \u0645\u0647\u062A\u0645\u0627\u064B \u0628\u0640 {interested} \u0628\u0645\u0646\u0627\u0633\u0628\u0629 \u0639\u064A\u062F \u0627\u0644\u0623\u0636\u062D\u0649. \u0627\u0643\u062A\u0628 \u0631\u0633\u0627\u0644\u0629 \u0627\u0633\u062A\u0631\u062F\u0627\u062F \u0634\u062E\u0635\u064A\u0629 \u0628\u0627\u0644\u062F\u0627\u0631\u062C\u0629 \u062A\u0630\u0643\u0631\u0647 \u0628\u0623\u0646 \u0627\u0644\u0631\u0642\u0645 \u0642\u062F \u064A\u0636\u064A\u0639 \u0645\u0639 \u0632\u062D\u0627\u0645 \u0627\u0644\u0639\u064A\u062F."
                followup = await get_live_llm_reply(prompt)
                await send_msg(phone, followup)
                logger.info(f"[RETENTION] Sent to {phone}")
        except Exception as e:
            logger.error(f"Retention error: {e}")
        await asyncio.sleep(300)


async def send_msg(to: str, text: str):
    try:
        resp = await http_client.post(
            WHATSAPP_API_URL,
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
        )
        if resp.status_code != 200:
            logger.error(f"Send failed {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Send exception to {to}: {e}")


async def mark_read(msg_id: str):
    try:
        await http_client.post(
            WHATSAPP_API_URL,
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
            json={"messaging_product": "whatsapp", "status": "read", "message_id": msg_id},
        )
    except Exception:
        pass


async def get_live_llm_reply(prompt: str, system_prompt: str = SALES_SYSTEM_PROMPT_BASE) -> str:
    reply = generate_conversational_reply(prompt, system_prompt)
    return sanitize_nim_response(reply)


def _classify_intent(msg: str, current_state: str) -> str:
    m = msg.lower().strip()
    if re.search(r"بوت|bot|روبوت", m):
        return "bot_query"
    if (
        re.search(
            r"زid|زيدني|زيدينا|الفوج|التالي|suite|suivant|next|ok|oui|نعم|اه|مزيد|ارسل|ابعث|بعث",
            m,
        )
        and current_state != State.NEW
    ):
        return "more_numbers"
    if re.search(r"0[67]\d{8}", re.sub(r"\s+", "", m)):
        return "interested_number"
    if re.search(r"اشتري|نشتري|بغيت|حجز|احجز|طلب|نطلب|توكل|نتوكل|نقاد|confirmer", m):
        return "buy_confirm"
    if re.search(r"غالي|تخفيض|نقص|نزل|السعر|شحال|prix|cher|réduction", m):
        return "negotiate"
    return "unknown"


@app.get("/health")
async def health():
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return {
        "status": "running",
        "version": "5.5.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {"status": "online", "service": "VIP Bot", "version": "5.5.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
