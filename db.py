import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from config import (
    MONGO_URI,
    MONGO_DB_NAME,
    MONGO_COLL_SESSIONS,
    MONGO_COLL_INVENTORY,
    MONGO_COLL_LOGS,
    SessionState,
)

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _client: Optional[MongoClient] = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            self._client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=20,
                minPoolSize=2,
                retryWrites=True,
                retryReads=True,
                w="majority",
            )
            self._client.admin.command("ping")
            logger.info("MongoDB Atlas connection established.")
        except PyMongoError as e:
            logger.critical(f"MongoDB Atlas connection failed: {e}")
            raise

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.info("MongoDB connection closed.")

    @property
    def db(self):
        if self._client is None:
            self.connect()
        return self._client[MONGO_DB_NAME]

    @property
    def sessions(self) -> Collection:
        return self.db[MONGO_COLL_SESSIONS]

    @property
    def inventory(self) -> Collection:
        return self.db[MONGO_COLL_INVENTORY]

    @property
    def logs(self) -> Collection:
        return self.db[MONGO_COLL_LOGS]

dbm = DatabaseManager()


def get_or_create_session(client_phone: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    default_session = {
        "client_phone": client_phone,
        "state": SessionState.NEW,
        "batch_cursor": 0,
        "last_interaction": now,
        "silence_started_at": None,
        "follow_up_sent": False,
        "interested_number": None,
        "quoted_price": None,
        "final_price": None,
        "client_name": None,
        "client_city": None,
        "created_at": now,
        "updated_at": now,
        "conversation_history": [],
    }
    try:
        result = dbm.sessions.find_one_and_update(
            {"client_phone": client_phone},
            {
                "$setOnInsert": default_session,
                "$set": {"last_interaction": now, "updated_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return result
    except PyMongoError as e:
        logger.error(f"MongoDB session upsert failed for {client_phone}: {e}")
        return default_session


def update_session_state(client_phone: str, new_state: str, extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    update_payload: Dict[str, Any] = {
        "$set": {"state": new_state, "last_interaction": now, "updated_at": now}
    }
    if extra_fields:
        for key, value in extra_fields.items():
            update_payload["$set"][key] = value
    try:
        result = dbm.sessions.find_one_and_update(
            {"client_phone": client_phone},
            update_payload,
            return_document=ReturnDocument.AFTER,
        )
        return result if result else {}
    except PyMongoError as e:
        logger.error(f"State update failed for {client_phone}: {e}")
        return {}


def advance_batch_cursor(client_phone: str) -> int:
    try:
        result = dbm.sessions.find_one_and_update(
            {"client_phone": client_phone},
            {"$inc": {"batch_cursor": 10}},
            return_document=ReturnDocument.AFTER,
        )
        return result.get("batch_cursor", 0) if result else 0
    except PyMongoError as e:
        logger.error(f"Batch cursor increment failed for {client_phone}: {e}")
        return 0


def set_silence_timer(client_phone: str) -> None:
    now = datetime.now(timezone.utc)
    dbm.sessions.update_one(
        {"client_phone": client_phone},
        {"$set": {"silence_started_at": now, "follow_up_sent": False, "updated_at": now}},
    )


def mark_follow_up_sent(client_phone: str) -> None:
    now = datetime.now(timezone.utc)
    dbm.sessions.update_one(
        {"client_phone": client_phone},
        {"$set": {"follow_up_sent": True, "updated_at": now}},
    )


def log_admin_operation(admin_phone: str, operation: str, details: str) -> None:
    dbm.logs.insert_one({
        "admin_phone": admin_phone,
        "operation": operation,
        "details": details,
        "timestamp": datetime.now(timezone.utc),
    })


def delete_number_from_inventory(phone_number: str) -> bool:
    try:
        result = dbm.inventory.delete_one({"number": phone_number})
        return result.deleted_count > 0
    except PyMongoError as e:
        logger.error(f"Failed to delete number {phone_number}: {e}")
        return False


def check_retention_eligibility(client_phone: str) -> Optional[Dict[str, Any]]:
    session = dbm.sessions.find_one({"client_phone": client_phone})
    if not session:
        return None
    silence_start = session.get("silence_started_at")
    follow_up_sent = session.get("follow_up_sent", False)
    if silence_start and not follow_up_sent:
        delta = datetime.now(timezone.utc) - silence_start
        if delta.total_seconds() >= 8 * 3600:
            return session
    return None
