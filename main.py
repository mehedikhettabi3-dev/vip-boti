from fastapi import FastAPI, Request, BackgroundTasks
from core.config import VERIFY_TOKEN
from core.database import init_db
from tasks.workflow_manager import process_incoming_message, check_and_send_followups
import asyncio

app = FastAPI(title="VIP Sales Bot", version="2.0.0")


@app.on_event("startup")
async def startup():
    init_db()
    asyncio.create_task(_followup_scheduler())


async def _followup_scheduler():
    while True:
        await asyncio.sleep(7200)
        try:
            await check_and_send_followups()
        except Exception as e:
            print(f"[Scheduler] followup error: {e}")


@app.get("/webhook")
async def verify_webhook(request: Request):
    try:
        query = request.query_params
        mode = query.get("hub.mode")
        token = query.get("hub.verify_token")
        challenge = query.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return int(challenge)
        return {"error": "Verification failed"}, 403
    except Exception:
        return {"error": "Server error"}, 500


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        entry = body.get("entry", [])
        for ent in entry:
            changes = ent.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    if msg.get("type") == "text":
                        phone = msg.get("from", "")
                        text = msg.get("text", {}).get("body", "")
                        if phone and text:
                            background_tasks.add_task(process_incoming_message, phone, text)
        return {"status": "success"}
    except Exception:
        return {"status": "success"}
