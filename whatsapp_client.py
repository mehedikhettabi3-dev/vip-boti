import logging
import time
from typing import Any, Dict

import requests

from config import WHATSAPP_API_URL, WHATSAPP_ACCESS_TOKEN

logger = logging.getLogger(__name__)


def send_whatsapp_message(to_phone: str, text_body: str) -> bool:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text_body},
    }
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id", "unknown")
                logger.info(f"Message sent to {to_phone} | ID: {message_id}")
                return True
            elif response.status_code == 429:
                wait = (2 ** attempt) * 2
                logger.warning(f"Rate limited for {to_phone}. Waiting {wait}s...")
                time.sleep(wait)
                continue
            else:
                logger.error(f"WhatsApp API error {response.status_code}: {response.text[:300]}")
                return False
        except requests.exceptions.Timeout:
            logger.error(f"Timeout sending to {to_phone} (attempt {attempt + 1})")
            if attempt < max_attempts - 1:
                time.sleep(2)
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to {to_phone}: {e}")
            return False
    logger.error(f"All {max_attempts} send attempts failed for {to_phone}")
    return False


def mark_message_as_read(message_id: str) -> None:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    try:
        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload, timeout=5)
        if response.status_code != 200:
            logger.warning(f"Failed to mark message {message_id} as read: {response.status_code}")
    except Exception as e:
        logger.warning(f"Exception marking message as read: {e}")
