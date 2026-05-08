import json
import requests
import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def test_whatsapp():
    print("[TEST] Checking WhatsApp API...")

    keys_path = Path(__file__).parent / "api_keys.json"
    with open(keys_path, "r", encoding="utf-8") as f:
        keys = json.load(f)
        token = keys.get("ACCESS_TOKEN")
        phone_id = keys.get("PHONE_NUMBER_ID")
        admin_phone = keys.get("ADMIN_PHONE", "212778375026")

    print(f"[INFO] Phone ID: {phone_id}")
    print(f"[INFO] Admin Phone: {admin_phone}")

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print(f"\n[TEST] Sending to: {admin_phone}")
    payload = {
        "messaging_product": "whatsapp",
        "to": admin_phone,
        "type": "text",
        "text": {
            "body": "✅ Test from check_wa.py - Bot is working! Is this reaching you?"
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 200:
        print("\n✅ SUCCESS! Message sent to your WhatsApp!")
    else:
        print(f"\n❌ Failed: {data.get('error', {}).get('message', 'Unknown')}")

if __name__ == "__main__":
    test_whatsapp()