import requests
import json

url = "https://vip-boti.onrender.com/webhook"
payload = {
    "object": "whatsapp_business_account",
    "entry": [{
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "contacts": [{"profile": {"name": "Antigravity Test Customer"}, "wa_id": "212600000000"}],
                "messages": [{
                    "from": "212600000000",
                    "text": {"body": "Salam, bghit nmra VIP 07 20 86 88 88"},
                    "type": "text"
                }]
            },
            "field": "messages"
        }]
    }]
}

print(f"🚀 Sending test message to {url}...")
try:
    response = requests.post(url, json=payload, timeout=10)
    print(f"✅ Status Code: {response.status_code}")
    print(f"📩 Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
