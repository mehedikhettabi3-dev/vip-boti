import motor.motor_asyncio
from datetime import datetime, timedelta
from core.config import MONGODB_URI, MONGODB_DB_NAME

_client = None
_db = None


def get_client():
    global _client
    if _client is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    return _client


def get_db():
    global _db
    if _db is None:
        client = get_client()
        _db = client[MONGODB_DB_NAME]
    return _db


def init_db():
    try:
        db = get_db()
        print(f"[DB] MongoDB connected to {MONGODB_DB_NAME}")
        print(f"[DB] Collections: users, conversations, purchases ready")
    except Exception as e:
        print(f"[DB] init error: {e}")


async def get_or_create_user(phone_number):
    try:
        db = get_db()
        user = await db.users.find_one({"phone_number": phone_number})
        if user is None:
            doc = {
                "phone_number": phone_number,
                "name": "",
                "city": "",
                "lead_score": 0,
                "status": "new",
                "last_interaction_time": datetime.utcnow(),
                "created_at": datetime.utcnow(),
            }
            await db.users.insert_one(doc)
            return doc
        return user
    except Exception as e:
        print(f"[DB] get_or_create_user error: {e}")
        return {"phone_number": phone_number, "name": "", "city": "", "lead_score": 0, "status": "new"}


async def save_message(phone_number, role, message):
    try:
        db = get_db()
        doc = {
            "phone_number": phone_number,
            "role": role,
            "message": message,
            "timestamp": datetime.utcnow(),
        }
        await db.conversations.insert_one(doc)
        await db.users.update_one(
            {"phone_number": phone_number},
            {"$set": {"last_interaction_time": datetime.utcnow()}},
        )
    except Exception as e:
        print(f"[DB] save_message error: {e}")


async def get_chat_history(phone_number, limit=5):
    try:
        db = get_db()
        cursor = db.conversations.find(
            {"phone_number": phone_number}
        ).sort("timestamp", -1).limit(limit)
        rows = await cursor.to_list(length=limit)
        result = []
        for row in reversed(rows):
            result.append({"role": row["role"], "message": row["message"]})
        return result
    except Exception as e:
        print(f"[DB] get_chat_history error: {e}")
        return []


async def update_lead_score(phone_number, score_delta):
    try:
        db = get_db()
        user = await db.users.find_one({"phone_number": phone_number})
        current_score = user.get("lead_score", 0) if user else 0
        new_score = current_score + score_delta
        new_status = "hot" if new_score >= 10 else (user.get("status", "new") if user else "new")
        await db.users.update_one(
            {"phone_number": phone_number},
            {"$set": {"lead_score": new_score, "status": new_status}},
        )
    except Exception as e:
        print(f"[DB] update_lead_score error: {e}")


async def update_user_city(phone_number, city):
    try:
        db = get_db()
        await db.users.update_one(
            {"phone_number": phone_number},
            {"$set": {"city": city}},
        )
    except Exception as e:
        print(f"[DB] update_user_city error: {e}")


async def get_users_by_status(status, min_days_old=3):
    try:
        db = get_db()
        cutoff = datetime.utcnow() - timedelta(days=min_days_old)
        pipeline = [
            {"$match": {"last_interaction_time": {"$lt": cutoff}}},
            {
                "$lookup": {
                    "from": "purchases",
                    "localField": "phone_number",
                    "foreignField": "phone_number",
                    "as": "purchases",
                }
            },
            {"$match": {"purchases": []}},
            {"$project": {"phone_number": 1, "_id": 0}},
        ]
        cursor = db.users.aggregate(pipeline)
        result = await cursor.to_list(length=1000)
        return [doc["phone_number"] for doc in result if "phone_number" in doc]
    except Exception as e:
        print(f"[DB] get_users_by_status error: {e}")
        return []


async def get_recent_buyers(hours_ago=24):
    try:
        db = get_db()
        cutoff = datetime.utcnow() - timedelta(hours=hours_ago)
        cursor = db.purchases.find(
            {"created_at": {"$gt": cutoff}},
            {"phone_number": 1, "_id": 0},
        )
        result = await cursor.to_list(length=1000)
        return [doc["phone_number"] for doc in result if "phone_number" in doc]
    except Exception as e:
        print(f"[DB] get_recent_buyers error: {e}")
        return []


async def get_inactive_users_since(hours=2):
    try:
        db = get_db()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        pipeline = [
            {"$match": {"last_interaction_time": {"$lt": cutoff}}},
            {
                "$lookup": {
                    "from": "purchases",
                    "localField": "phone_number",
                    "foreignField": "phone_number",
                    "as": "purchases",
                }
            },
            {"$match": {"purchases": []}},
            {"$project": {"phone_number": 1, "_id": 0}},
        ]
        cursor = db.users.aggregate(pipeline)
        result = await cursor.to_list(length=1000)
        return [doc["phone_number"] for doc in result if "phone_number" in doc]
    except Exception as e:
        print(f"[DB] get_inactive_users_since error: {e}")
        return []


async def add_purchase(phone_number, purchased_number, referral_code=""):
    try:
        db = get_db()
        doc = {
            "phone_number": phone_number,
            "purchased_number": purchased_number,
            "referral_code": referral_code,
            "created_at": datetime.utcnow(),
        }
        await db.purchases.insert_one(doc)
    except Exception as e:
        print(f"[DB] add_purchase error: {e}")
