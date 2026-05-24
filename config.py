import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", os.getenv("META_PHONE_ID", ""))
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", os.getenv("META_TOKEN", ""))
WHATSAPP_API_VERSION = "v21.0"
WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", os.getenv("VERIFY_TOKEN", "MehediVip2026"))

MONGO_URI = os.getenv("MONGO_URI", os.getenv("MONGODB_URI", ""))
MONGO_DB_NAME = "vip_numbers_bot"
MONGO_COLL_SESSIONS = "client_sessions"
MONGO_COLL_INVENTORY = "phone_inventory"
MONGO_COLL_LOGS = "system_logs"

NVIDIA_NIM_BASE_URL = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY", os.getenv("NVIDIA_API_KEY", ""))
NVIDIA_NIM_MODEL = os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_NIM_MAX_TOKENS = 600
NVIDIA_NIM_TEMPERATURE = 0.3
NVIDIA_NIM_TIMEOUT_SECONDS = 12

ADMIN_PHONE = "212778375026"
