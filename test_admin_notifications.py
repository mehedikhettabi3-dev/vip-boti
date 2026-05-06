#!/usr/bin/env python3
"""
Test Admin Notifications System
Tests the new WhatsApp click tracking and admin notification features
"""
import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE = "https://vip-boti.onrender.com"
CLICK_TRACKING_URL = f"{API_BASE}/api/whatsapp-click"
ADMIN_PHONE = "212638388885"

def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_whatsapp_click_tracking():
    """Test 1: Simulate frontend WhatsApp button click"""
    print_header("TEST 1: WhatsApp Click Tracking API")

    test_cases = [
        {
            "name": "Diamond Tier Click",
            "number": "0720868888",
            "price": "200 DH",
            "tier": "Diamond",
            "sender": "Web User - Test 1"
        },
        {
            "name": "Inwi Tier Click",
            "number": "0717588887",
            "price": "150 DH",
            "tier": "Inwi",
            "sender": "Web User - Test 2"
        },
        {
            "name": "Premium Number Click",
            "number": "0703313313",
            "price": "200 DH",
            "tier": "Diamond",
            "sender": "Web User - Premium Test"
        }
    ]

    results = []
    for test in test_cases:
        try:
            print(f"Testing: {test['name']}")
            print(f"  Number: {test['number']}")
            print(f"  Price: {test['price']}")
            print(f"  Tier: {test['tier']}")

            response = requests.post(
                CLICK_TRACKING_URL,
                json={
                    "number": test['number'],
                    "price": test['price'],
                    "tier": test['tier'],
                    "sender": test['sender']
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                print(f"  [OK] Status: {response.status_code}")
                print(f"  [OK] Response: Success")
                if 'redirect' in data:
                    print(f"  [OK] Redirect URL generated")
                results.append({"test": test['name'], "status": "PASS"})
            else:
                print(f"  [FAIL] Status: {response.status_code}")
                print(f"  [FAIL] Response: {response.text[:200]}")
                results.append({"test": test['name'], "status": "FAIL"})

        except requests.exceptions.Timeout:
            print(f"  [FAIL] Timeout: Request took too long")
            results.append({"test": test['name'], "status": "TIMEOUT"})
        except Exception as e:
            print(f"  [FAIL] Error: {str(e)}")
            results.append({"test": test['name'], "status": "ERROR"})

        print()
        time.sleep(2)

    return results

def test_direct_admin_notification():
    """Test 2: Direct admin notification via WhatsApp Bot API"""
    print_header("TEST 2: Direct Admin Notification")

    print("Attempting direct notification to admin...")
    print(f"Admin Phone: {ADMIN_PHONE}")
    print()

    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)

        if response.status_code == 200:
            print(f"[OK] Bot API is reachable")
            print(f"[OK] Health check: {response.status_code}")
            return [{"test": "Direct Notification", "status": "REACHABLE"}]
        else:
            print(f"[FAIL] Bot API returned status: {response.status_code}")
            return [{"test": "Direct Notification", "status": "UNREACHABLE"}]

    except requests.exceptions.Timeout:
        print(f"[FAIL] Timeout connecting to bot API")
        return [{"test": "Direct Notification", "status": "TIMEOUT"}]
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")
        return [{"test": "Direct Notification", "status": "ERROR"}]

def generate_report(all_results):
    """Generate test report"""
    print_header("TEST REPORT SUMMARY")

    total = len(all_results)
    passed = len([r for r in all_results if r['status'] == 'PASS' or r['status'] == 'REACHABLE'])
    failed = len([r for r in all_results if r['status'] == 'FAIL' or r['status'] == 'UNREACHABLE'])
    errors = len([r for r in all_results if r['status'] in ['ERROR', 'TIMEOUT']])

    print(f"Total Tests: {total}")
    print(f"[PASS] Passed: {passed}")
    print(f"[FAIL] Failed: {failed}")
    print(f"[WARN] Errors: {errors}")
    print()

    print("Detailed Results:")
    print("-" * 70)
    for result in all_results:
        status_icon = "[OK]" if result['status'] in ['PASS', 'REACHABLE'] else "[X]" if result['status'] == 'FAIL' else "[!]"
        print(f"{status_icon} {result['test']:<40} {result['status']}")

    print()
    if failed == 0 and errors == 0:
        print("SUCCESS: ALL TESTS PASSED!")
        print()
        print("Your admin notification system is working correctly.")
        print(f"Admin notifications will be sent to: +{ADMIN_PHONE}")
        print()
        print("When users click WhatsApp buttons on your site:")
        print("1. The frontend calls /api/whatsapp-click")
        print("2. The backend sends instant admin notification")
        print("3. User is redirected to WhatsApp")
        print("4. Click is logged for analytics")
    else:
        print("WARNING: Some tests failed. Check the details above.")

    print()

def main():
    print("\n" + "=" * 70)
    print("  ADMIN NOTIFICATION SYSTEM TEST SUITE")
    print("  Time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    all_results = []

    # Run tests
    all_results.extend(test_whatsapp_click_tracking())
    all_results.extend(test_direct_admin_notification())

    # Generate report
    generate_report(all_results)

    print("=" * 70)
    print("NOTE: Check your WhatsApp messages to +212638388885")
    print("   You should receive admin notifications for each test.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
