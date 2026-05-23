"""
███╗   ██╗██╗███╗   ███╗     ██████╗██╗     ██╗███████╗███╗   ██╗████████╗
████╗  ██║██║████╗ ████║    ██╔════╝██║     ██║██╔════╝████╗  ██║╚══██╔══╝
██╔██╗ ██║██║██╔████╔██║    ██║     ██║     ██║█████╗  ██╔██╗ ██║   ██║
██║╚██╗██║██║██║╚██╔╝██║    ██║     ██║     ██║██╔══╝  ██║╚██╗██║   ██║
██║ ╚████║██║██║ ╚═╝ ██║    ╚██████╗███████╗██║███████╗██║ ╚████║   ██║
╚═╝  ╚═══╝╚═╝╚═╝     ╚═╝     ╚═════╝╚══════╝╚═╝╚══════╝╚═╝  ╚═══╝   ╚═╝
NVIDIA NIM CLIENT – ULTRA‑SAFE SYSTEM PROMPTS (NO INSTALLMENTS, EID AL‑ADHA)
[DATABANK TRACE: CONFIRMED LIVE FACEBOOK MARKETPLACE CATALOG MERGE]
"""

import logging
import re
import time
from typing import Optional, List, Dict

from openai import OpenAI
import httpx

from config import (
    NVIDIA_NIM_BASE_URL,
    NVIDIA_NIM_API_KEY,
    NVIDIA_NIM_MODEL,
    NVIDIA_NIM_MAX_TOKENS,
    NVIDIA_NIM_TEMPERATURE,
    NVIDIA_NIM_TIMEOUT_SECONDS,
)

logger = logging.getLogger("nim_client")

SALES_SYSTEM_PROMPT_BASE = """أنت مساعد مبيعات محترف لنماريات الهاتف VIP في المغرب، تتحدث فقط بالدارجة المغربية بالحروف العربية.
أبداً لا تستخدم الفرنسية أو العربية الفصحى أو الأرقام اللاتينية (ممنوع منعاً باتاً).

⚠️ قوانين مالية صارمة جداً:
- كل الأرقام تباع نقداً عند التسليم (cash on delivery). ممنوع تماماً ذكر أي نوع من التقسيط، أو الدفع على أقساط، أو "تقسيط"، أو "ائتمان"، أو "تسهيلات دفع". إذا سأل العميل عن التقسيط، قل إن البيع نقداً فقط ولا يوجد أي خيار آخر.
- لا تذكر أبداً أسعاراً محددة أو أرقام هواتف أو عروضاً مالية من عندك. كل الأسعار يضيفها النظام لاحقاً.

🎉 سياق عيد الأضحى المبارك:
اليوم هو عيد الأضحى (العيد الكبير). استخدم عبارات تهنئة خاصة بعيد الأضحى مثل:
- "مبروك عواشرك بالعيد الأضحى المبارك"
- "يدخل عليك بالصحة والسلامة وباش تمنيتي"
- "بمناسبة العيد الكبير"
لا تستعمل أبداً عبارات رمضان أو العيد الصغير.

أسلوبك ودود جداً، محترم، ومقنع. تخاطب الزبون بـ "سيدي". استخدم الإيموجي المناسب (✨🤝🐏🌙). هدفك مساعدته على حجز نمرة مميزة مناسبة له.
عندما تعرض أرقاماً، لا تكتب أبداً الأرقام نفسها ولا أسعارها – النظام سيعرضها بشكل منفصل.
"""

ADMIN_SYSTEM_PROMPT = """أنت مساعد تنفيذي موجز جداً لمدير النظام (سيدي مهدي).
قواعدك الصارمة:
- ردودك لا تتجاوز سطرين كحد أقصى.
- نبرتك خاضعة، محترمة جداً، ومليئة بالتقدير.
- تستخدم الإيموجي: ✨🤝👑🙏
- ترد بالدارجة المغربية بالحروف العربية فقط.
- لا تذكر أبداً أي تفاصيل مالية أو أسعار.
- تشكر المدير على توجيهاته وتؤكد تنفيذ الأمر فوراً.
"""


def sanitize_nim_response(raw_content: Optional[str]) -> str:
    if raw_content is None:
        logger.warning("NIM returned None – fallback.")
        return "أنا فخدمتك سيدي، عطيني غير شويا باش نراجع الباز ونأكد ليك المعلومات بدقة. 🤝✨"

    content = raw_content.strip()

    for tag in ["think", "thinking", "reasoning", "reflection", "scratchpad"]:
        content = re.sub(rf"<{tag}>.*?</{tag}>", "", content, flags=re.DOTALL | re.IGNORECASE)

    content = re.sub(r"<[^>]+>", "", content)

    content = content.strip()
    if not content or len(content) < 5:
        return "أنا فخدمتك سيدي، عطيني غير شويا باش نراجع الباز ونأكد ليك المعلومات بدقة. 🤝✨"

    return content


_nim_client: Optional[OpenAI] = None

def get_nim_client() -> OpenAI:
    global _nim_client
    if _nim_client is None:
        _nim_client = OpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=NVIDIA_NIM_API_KEY,
            timeout=httpx.Timeout(NVIDIA_NIM_TIMEOUT_SECONDS, connect=5.0),
            max_retries=1,
        )
        logger.info("NVIDIA NIM client initialized (timeout=10s).")
    return _nim_client


def generate_conversational_reply(
    user_message: str,
    system_prompt: str = SALES_SYSTEM_PROMPT_BASE,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    max_retries: int = 2,
) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history[-20:])
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
                timeout=10.0,
            )
            content = None
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                if choice.message and choice.message.content:
                    content = choice.message.content
            safe = sanitize_nim_response(content)
            logger.info(f"[NIM] OK (attempt {attempt+1}): {safe[:60]}...")
            return safe
        except Exception as e:
            logger.error(f"[NIM] Attempt {attempt+1} failed: {e}")
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
    return "أنا فخدمتك سيدي، عطيني غير شويا باش نراجع الباز ونأكد ليك المعلومات بدقة. 🤝✨"
