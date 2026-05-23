import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path)

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_NIM_ENDPOINT = os.getenv("NVIDIA_NIM_ENDPOINT", "https://api.nvcf.nim.llm.nvidia.com/v1/chat/completions")
NVIDIA_NIM_MODEL = os.getenv("NVIDIA_NIM_MODEL", "meta/llama3-70b-instruct")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "vip_sales_bot")

META_TOKEN = os.getenv("META_TOKEN", "")
META_PHONE_ID = os.getenv("META_PHONE_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
