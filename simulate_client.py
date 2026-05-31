#!/usr/bin/env python3
"""
Simulate a Meta Cloud API webhook payload to test the bot locally.
Fires a mock client message ("salam") to your local Flask server
and checks if the admin notification logic triggers.
"""
import requests
import json
import sys
import time
import os

# Adjust port if your local Flask runs on a different port
PORT = os.environ.get("PORT", "5000")
WEBHOOK_URL = f"http://localhost:{PORT}/webhook"
DUMMY_SENDER = "212600000000"
DUMMY_NAME = "Client Test"

payload = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "123456",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "212600000001",
                    "phone_number_id": "123456789"
                },
                "contacts": [{
                    "profile": {"name": DUMMY_NAME},
                    "wa_id": DUMMY_SENDER
                }],
                "messages": [{
                    "from": DUMMY_SENDER,
                    "id": f"test_msg_{int(time.time())}",
                    "timestamp": str(int(time.time())),
                    "text": {"body": "salam"},
                    "type": "text"
                }]
            },
            "field": "messages"
        }]
    }]
}

print(f"Sending mock Meta webhook payload to {WEBHOOK_URL}")
print(f"  From: {DUMMY_SENDER} ({DUMMY_NAME})")
print(f"  Message: \"salam\"")
print()

try:
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=15)
    print(f"HTTP {resp.status_code}")
    if resp.status_code == 200:
        print("Bot accepted the webhook payload.")
        print()
        print("Check your Flask terminal logs for:")
        print("  [WEBHOOK RAW] ... (incoming payload)")
        print("  [SYSTEM] Lead alert sent to ... (admin notification sent)")
        print("  handle_logic reply (bot's response to the client)")
        print()
        print("If you see all three, the admin notification flow works.")
    else:
        print(f"Unexpected response: {resp.text[:300]}")
        sys.exit(1)
except requests.ConnectionError:
    print(f"Cannot connect to {WEBHOOK_URL}")
    print("Make sure your Flask bot is running locally:")
    print("  cd vip-boti && python whatsapp_bot.py")
    print("  (or: gunicorn -w 2 -b 0.0.0.0:5000 whatsapp_bot:app)")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
