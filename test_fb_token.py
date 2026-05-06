import json
import requests
import os

def test_fb():
    print("🔍 Testing Facebook / WhatsApp API...")
    
    # Try to load api_keys.json
    try:
        with open("api_keys.json", "r") as f:
            keys = json.load(f)
            token = keys.get("ACCESS_TOKEN")
            phone_id = keys.get("PHONE_NUMBER_ID")
            admin_phone = keys.get("ADMIN_PHONE")
    except Exception as e:
        print(f"❌ Error reading api_keys.json: {e}")
        return

    if not token or not phone_id:
        print("❌ Missing ACCESS_TOKEN or PHONE_NUMBER_ID in api_keys.json")
        return

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Ask the user for a phone number to send a test message to
    test_number = input(f"📱 Enter your WhatsApp number with country code (e.g. {admin_phone}): ").strip()
    if not test_number:
        test_number = admin_phone

    payload = {
        "messaging_product": "whatsapp",
        "to": test_number,
        "type": "text",
        "text": {"body": "🔔 Test message from VIP Bot! If you see this, the Facebook API is working perfectly."}
    }

    print(f"\n⏳ Sending request to Meta API...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"\n📊 Status Code: {response.status_code}")
        
        resp_json = response.json()
        print(f"📝 Response Data: {json.dumps(resp_json, indent=2)}")
        
        if response.status_code in (200, 201):
            print("\n✅ SUCCESS! The message was accepted by Facebook.")
        else:
            print("\n❌ FAILED! Facebook rejected the message.")
            if "error" in resp_json:
                err = resp_json["error"]
                if err.get("code") == 190:
                    print("⚠️ REASON: Your ACCESS_TOKEN has expired! Meta temporary tokens expire after 24 hours. You need to create a System User and get a permanent token.")
                elif err.get("code") == 131030:
                    print("⚠️ REASON: You are using a Test Phone Number and the recipient number is not verified in the Meta Developer Dashboard.")
                else:
                    print(f"⚠️ REASON: {err.get('message')}")
                    
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_fb()
    input("\nPress Enter to exit...")
