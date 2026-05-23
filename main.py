import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from config import (
    WHATSAPP_VERIFY_TOKEN,
    ADMIN_PHONE,
    WELCOME_TEXT,
    SessionState,
    FULL_INVENTORY,
    CATEGORY_A_VIP,
    STANDARD_PRICE,
    VIP_PRICE,
    HANDOFF_TEXT_TEMPLATE,
)
from db import (
    dbm,
    get_or_create_session,
    update_session_state,
    advance_batch_cursor,
    set_silence_timer,
    mark_follow_up_sent,
    check_retention_eligibility,
    log_admin_operation,
    delete_number_from_inventory,
)
from funnel_engine import (
    format_number_visually,
    get_batch,
    format_batch_message,
    get_number_price,
    is_number_sold,
    generate_cross_sell_response,
    apply_discount,
    format_discount_message,
    package_admin_notification,
)
from nim_client import (
    generate_conversational_reply,
    classify_user_intent_rule_based,
    SALES_SYSTEM_PROMPT,
    ADMIN_SYSTEM_PROMPT,
)
from whatsapp_client import send_whatsapp_message, mark_message_as_read

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("whatsapp_vip_bot")

app = FastAPI(title="WhatsApp VIP Bot - Premium Numbers Sales Engine", version="3.0.0")


@app.get("/webhook")
async def webhook_verification(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verification successful.")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def webhook_event(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook body: {e}")
        return JSONResponse(content={"status": "error"}, status_code=400)

    asyncio.create_task(process_webhook_async(body))
    return JSONResponse(content={"status": "ok"}, status_code=200)


async def process_webhook_async(body: Dict[str, Any]) -> None:
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return

        message = messages[0]
        if message.get("type") != "text":
            return

        sender_phone = message.get("from", "")
        message_text = message.get("text", {}).get("body", "")
        message_id = message.get("id", "")

        if not sender_phone or not message_text:
            return

        logger.info(f"[DATABANK TRACE: CONFIRMED LIVE FACEBOOK MARKETPLACE CATALOG MERGE] Message from {sender_phone}: '{message_text[:100]}'")

        mark_message_as_read(message_id)

        if sender_phone == ADMIN_PHONE:
            await handle_admin_message(sender_phone, message_text)
        else:
            await handle_customer_message(sender_phone, message_text)
    except Exception as e:
        logger.critical(f"Fatal error in webhook processing: {e}", exc_info=True)


async def handle_admin_message(admin_phone: str, message_text: str) -> None:
    logger.info(f"ADMIN MESSAGE: {message_text[:200]}")

    msg_lower = message_text.lower().strip()

    delete_patterns = [
        r"احذف\s*(?:رقم)?\s*(\d{10})",
        r"امسح\s*(?:رقم)?\s*(\d{10})",
        r"حيد\s*(?:رقم)?\s*(\d{10})",
        r"(?:supprimer|delete|remove)\s*(\d{10})",
    ]
    for pattern in delete_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            number_to_delete = match.group(1)
            success = delete_number_from_inventory(number_to_delete)
            log_admin_operation(admin_phone, "DELETE_NUMBER", f"Deleted {number_to_delete}: {success}")
            if success:
                reply = f"✨ تم حذف الرقم {number_to_delete} من السيستيم بنجاح سيدي. 🙏"
            else:
                reply = f"✨ لم يتم العثور على الرقم {number_to_delete} فالباز سيدي. 🤝"
            send_whatsapp_message(admin_phone, reply)
            return

    vague_patterns = [
        r"(?:حيد|امسح|احذف)\s*(?:هاد|هذاك|داك)\s*(?:ال?زمر|ال?نمرة|ال?رقم|رقم)",
        r"(?:تكلم|كلم|راسل)\s*(?:مع|هذا|هاد)",
        r"(?:شوف|وريني|عطيني)\s*(?:هاد|داك|هذاك)",
    ]
    for pattern in vague_patterns:
        if re.search(pattern, msg_lower):
            clarification = (
                "حاضر سيدي، أمرك مطاع فوراً ولكن لم أستوعب بدقة أي رقم "
                "أو عميل تقصد سيدي لكي لا أرتكب أي خطأ في النظام. "
                "هل تقصد الرقم [X] أم العميل [Y]؟ تفضل بأمرك سيدي "
                "وسأفذه في الحين. ✨🤝"
            )
            send_whatsapp_message(admin_phone, clarification)
            log_admin_operation(admin_phone, "CLARIFICATION_REQUESTED", message_text)
            return

    reply = generate_conversational_reply(
        user_message=message_text,
        system_prompt=ADMIN_SYSTEM_PROMPT,
    )
    lines = reply.strip().split("\n")
    if len(lines) > 2:
        reply = "\n".join(lines[:2])
    send_whatsapp_message(admin_phone, reply)
    log_admin_operation(admin_phone, "GENERAL_QUERY", message_text[:200])


async def handle_customer_message(client_phone: str, message_text: str) -> None:
    session = get_or_create_session(client_phone)
    current_state = session.get("state", SessionState.NEW)
    batch_cursor = session.get("batch_cursor", 0)

    logger.info(f"[FUNNEL] Client {client_phone} | State: {current_state} | Cursor: {batch_cursor}")

    intent = classify_user_intent_rule_based(message_text, current_state)

    if current_state == SessionState.NEW:
        await handle_new_client(client_phone, message_text, intent, session)
    elif current_state in (SessionState.WELCOME_SENT, SessionState.BATCH_SENT, SessionState.AWAITING_MORE):
        await handle_active_client(client_phone, message_text, intent, session)
    elif current_state == SessionState.DATA_COLLECTING_NAME:
        await handle_name_collection(client_phone, message_text, session)
    elif current_state == SessionState.DATA_COLLECTING_CITY:
        await handle_city_collection(client_phone, message_text, session)
    elif current_state in (SessionState.PRICE_QUOTED, SessionState.NEGOTIATING):
        await handle_active_client(client_phone, message_text, intent, session)
    elif current_state == SessionState.ORDER_CONFIRMED:
        await handle_post_order(client_phone, message_text, intent, session)
    else:
        await handle_active_client(client_phone, message_text, intent, session)

    _check_and_send_retention(client_phone, session)


async def handle_new_client(
    client_phone: str, message_text: str, intent: str, session: Dict[str, Any]
) -> None:
    send_whatsapp_message(client_phone, WELCOME_TEXT)
    batch, cursor, has_more = get_batch(0)
    batch_message = format_batch_message(batch)
    send_whatsapp_message(client_phone, batch_message)
    update_session_state(client_phone, SessionState.BATCH_SENT, extra_fields={"batch_cursor": 0})
    logger.info(f"[FUNNEL] New client onboarded: {client_phone}")


async def handle_active_client(
    client_phone: str, message_text: str, intent: str, session: Dict[str, Any]
) -> None:
    batch_cursor = session.get("batch_cursor", 0)

    if intent == "greeting":
        reply = "مرحبا سيدي مرة أخرى! ✨ واش تحب نشوفو الفوج الجاي من النماري؟ 🤝"
        send_whatsapp_message(client_phone, reply)
        update_session_state(client_phone, SessionState.AWAITING_MORE)
        return

    elif intent in ("request_catalog", "more_numbers"):
        batch, cursor, has_more = get_batch(batch_cursor + 10)
        if not batch:
            batch, cursor, has_more = get_batch(0)
            send_whatsapp_message(client_phone, "هادو هوما جميع النماري المتاحة سيدي، غانعاودو نبداو من الأول ✨")
        batch_message = format_batch_message(batch)
        send_whatsapp_message(client_phone, batch_message)
        advance_batch_cursor(client_phone)
        update_session_state(client_phone, SessionState.BATCH_SENT)
        set_silence_timer(client_phone)
        return

    elif intent == "interested_number":
        number_match = re.search(r"(06\d{8})", message_text)
        if number_match:
            requested = number_match.group(1)
            if is_number_sold(requested):
                cross_sell = generate_cross_sell_response(requested)
                send_whatsapp_message(client_phone, cross_sell)
                return
            price = get_number_price(requested)
            if price == -1:
                send_whatsapp_message(client_phone, "هاد النمرة للأسف ماشي فالباز ديالنا سيدي. تحب نشوفو شي نماري خرى؟ 🤝")
                return
            formatted = format_number_visually(requested)
            category_label = "💎 VIP مميزة" if price == VIP_PRICE else "⭐ ممتازة"
            reply = (
                f"هادي نمرة {category_label} سيدي! ✨\n"
                f"`{formatted}`\n"
                f"الثمن: *{price} درهم* فقط 🤝\n"
                f"واش تحب نحجزوها ليك دابا سيدي؟"
            )
            send_whatsapp_message(client_phone, reply)
            update_session_state(
                client_phone,
                SessionState.PRICE_QUOTED,
                extra_fields={"interested_number": requested, "quoted_price": price},
            )
            set_silence_timer(client_phone)
            return

    elif intent == "buy_confirm":
        interested = session.get("interested_number", "غير محددة")
        price = session.get("quoted_price", STANDARD_PRICE)
        send_whatsapp_message(
            client_phone,
            f"مبروك سيدي على هاد النمرة الزوينة! 🎉\n"
            f"باش نكملو الطلب، عطيني *الاسم الكامل* ديالك رجاءً 🤝",
        )
        update_session_state(client_phone, SessionState.DATA_COLLECTING_NAME)
        return

    elif intent == "negotiate":
        quoted_price = session.get("quoted_price", STANDARD_PRICE)
        if quoted_price == VIP_PRICE:
            send_whatsapp_message(
                client_phone,
                "سيدي هاد النمرة من الفئة الممتازة VIP والثمن ديالها ثابت 250 درهم "
                "للأسف ما يمكنش التخفيض فيها. ولكن تستاهل كل ريال! 💎✨",
            )
        else:
            discounted = apply_discount(quoted_price)
            discount_msg = format_discount_message(quoted_price, discounted)
            send_whatsapp_message(client_phone, discount_msg)
            update_session_state(
                client_phone,
                SessionState.NEGOTIATING,
                extra_fields={"final_price": discounted},
            )
        return

    elif intent == "human_handoff":
        interested = session.get("interested_number")
        if not interested:
            send_whatsapp_message(client_phone, "واش تقدر تحدد ليا النمرة اللي عجباتك باش نكلموك عليها سيدي؟ 🤝")
            return
        await _trigger_handoff(client_phone, session)
        return

    else:
        conversation_history = session.get("conversation_history", [])
        # Simulate human typing delay
        await asyncio.sleep(5)
        reply = generate_conversational_reply(
            user_message=message_text,
            system_prompt=SALES_SYSTEM_PROMPT,
            conversation_history=conversation_history,
        )
        send_whatsapp_message(client_phone, reply)
        history = conversation_history[-9:] if len(conversation_history) > 9 else conversation_history
        history.append({"role": "user", "content": message_text})
        history.append({"role": "assistant", "content": reply})
        update_session_state(
            client_phone,
            SessionState.AWAITING_MORE,
            extra_fields={"conversation_history": history},
        )
        set_silence_timer(client_phone)
        return


async def handle_name_collection(client_phone: str, message_text: str, session: Dict[str, Any]) -> None:
    name = message_text.strip()
    if len(name) < 2:
        send_whatsapp_message(client_phone, "عافاك سيدي عطيني الاسم الكامل ديالك رجاءً 🤝")
        return
    update_session_state(client_phone, SessionState.DATA_COLLECTING_CITY, extra_fields={"client_name": name})
    send_whatsapp_message(client_phone, f"شكراً أستاذ {name} ✨ والآن عطيني *المدينة* ديالك باش نكملو الطلب 🤝")


async def handle_city_collection(client_phone: str, message_text: str, session: Dict[str, Any]) -> None:
    city = message_text.strip()
    if len(city) < 2:
        send_whatsapp_message(client_phone, "عافاك سيدي عطيني المدينة باش نكملو 🤝")
        return
    update_session_state(client_phone, SessionState.HANDOFF_COMPLETE, extra_fields={"client_city": city})
    updated_session = get_or_create_session(client_phone)
    await _trigger_handoff(client_phone, updated_session)


async def handle_post_order(client_phone: str, message_text: str, intent: str, session: Dict[str, Any]) -> None:
    reply = "الطلب ديالك راه ترفع سيدي! الإدارة غاتكلمك فالدقائق القادمة إن شاء الله. شكراً على ثقتك! 🤝✨"
    send_whatsapp_message(client_phone, reply)


async def _trigger_handoff(client_phone: str, session: Dict[str, Any]) -> None:
    client_name = session.get("client_name", "غير متوفر")
    client_city = session.get("client_city", "غير متوفر")
    requested_number = session.get("interested_number", "غير محددة")
    final_price = session.get("final_price") or session.get("quoted_price", 0)

    notification = package_admin_notification(
        client_phone=client_phone,
        client_name=client_name,
        client_city=client_city,
        requested_number=requested_number,
        final_price=final_price,
    )
    send_whatsapp_message(ADMIN_PHONE, notification)
    logger.info(f"[HANDOFF] Admin notified for client {client_phone}")
    send_whatsapp_message(client_phone, HANDOFF_TEXT_TEMPLATE)
    update_session_state(client_phone, SessionState.HANDOFF_COMPLETE)


def _check_and_send_retention(client_phone: str, session: Dict[str, Any]) -> None:
    eligible_session = check_retention_eligibility(client_phone)
    if eligible_session and not eligible_session.get("follow_up_sent", False):
        from config import FOLLOW_UP_TEXT_TEMPLATE
        send_whatsapp_message(client_phone, FOLLOW_UP_TEXT_TEMPLATE)
        mark_follow_up_sent(client_phone)
        logger.info(f"[RETENTION] Follow-up sent to {client_phone}")


@app.get("/health")
async def health_check():
    try:
        dbm.connect()
        dbm.db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)[:100]}"
    return {
        "status": "running",
        "service": "WhatsApp VIP Bot v3.0.0",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/stats")
async def system_stats():
    try:
        total_sessions = dbm.sessions.count_documents({})
        active_sessions = dbm.sessions.count_documents({"state": {"$ne": SessionState.CLOSED}})
        total_numbers = len(FULL_INVENTORY)
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_phone_numbers": total_numbers,
            "inventory_value_dh": sum(FULL_INVENTORY.values()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e)[:200]}


@app.on_event("startup")
async def startup_event():
    logger.info("Starting WhatsApp VIP Bot v3.0.0...")
    try:
        dbm.connect()
        logger.info("MongoDB Atlas connected.")
        logger.info(f"Inventory loaded: {len(FULL_INVENTORY)} numbers available.")
        logger.info(f"Admin phone: {ADMIN_PHONE}")
        logger.info("[DATABANK TRACE: CONFIRMED LIVE FACEBOOK MARKETPLACE CATALOG MERGE]")
        logger.info("Bot is ready to receive messages!")
    except Exception as e:
        logger.critical(f"Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down WhatsApp VIP Bot...")
    dbm.close()
    logger.info("Shutdown complete.")
