import requests
import time
import random
from core.config import META_TOKEN, META_PHONE_ID

META_API_URL = f"https://graph.facebook.com/v18.0/{META_PHONE_ID}/messages"


class WhatsAppAPI:

    @staticmethod
    def _headers():
        return {
            "Authorization": f"Bearer {META_TOKEN}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _human_typing_delay():
        delay = random.uniform(3.0, 5.0)
        time.sleep(delay)

    @staticmethod
    def send_text(phone, text):
        WhatsAppAPI._human_typing_delay()
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": text},
            }
            resp = requests.post(META_API_URL, headers=WhatsAppAPI._headers(), json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"[WhatsApp] send_text error: {e}")
            return False

    @staticmethod
    def send_typing_indicator(phone, duration_seconds=4):
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": ". . ."},
            }
            requests.post(META_API_URL, headers=WhatsAppAPI._headers(), json=payload, timeout=10)
            time.sleep(duration_seconds)
            return True
        except Exception as e:
            print(f"[WhatsApp] send_typing_indicator error: {e}")
            return False

    @staticmethod
    def send_voice_note(phone, audio_id):
        WhatsAppAPI._human_typing_delay()
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "audio",
                "audio": {"id": audio_id},
            }
            resp = requests.post(META_API_URL, headers=WhatsAppAPI._headers(), json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"[WhatsApp] send_voice_note error: {e}")
            return False

    @staticmethod
    def send_interactive_buttons(phone, text, buttons_list):
        WhatsAppAPI._human_typing_delay()
        try:
            buttons = []
            for i, btn in enumerate(buttons_list[:3]):
                buttons.append({
                    "type": "reply",
                    "reply": {"id": f"btn_{i}", "title": btn},
                })
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": text},
                    "action": {"buttons": buttons},
                },
            }
            resp = requests.post(META_API_URL, headers=WhatsAppAPI._headers(), json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"[WhatsApp] send_interactive_buttons error: {e}")
            return False
