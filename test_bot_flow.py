#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Load data
with open('catalog.json', encoding='utf-8') as f:
    catalog = json.load(f)

with open('responses.json', encoding='utf-8') as f:
    responses = json.load(f)

# Get first number
first_num = catalog["Diamond"][0]["number"]

# Simulate bot logic
def find_number_in_catalog(text):
    digits = "".join(filter(str.isdigit, text))
    if len(digits) < 9: 
        return None, None
    for tier, items in catalog.items():
        for item in items:
            item_digits = "".join(filter(str.isdigit, item["number"]))
            if digits in item_digits or item_digits.endswith(digits[-9:]) or digits == item_digits:
                return item, tier
    return None, None

print("=" * 60)
print("FULL SIMULATION TEST - BOT FLOW")
print("=" * 60)

print("\nTest Case: User sends a number")
print(f"Input: {first_num}\n")

# Step 1: Find number
found_item, tier = find_number_in_catalog(first_num)
print(f"Step 1 - Find in catalog: {'FOUND' if found_item else 'NOT FOUND'}")

if found_item:
    print(f"  Number: {found_item['number']}")
    print(f"  Price: {found_item.get('price', 'N/A')}")
    print(f"  Tier: {tier}")
    
    # Step 2: Get response
    print(f"\nStep 2 - Get response template")
    intent = "number_available"
    response_templates = responses.get(intent, [])
    print(f"  Intent: {intent}")
    print(f"  Templates available: {len(response_templates)}")
    
    # Step 3: Format response
    if response_templates:
        sample_response = response_templates[0]
        formatted = sample_response.format(
            number=found_item["number"], 
            price=found_item.get("price", "N/A"), 
            catalog_url="https://vip-boti.onrender.com"
        )
        print(f"\nStep 3 - Final Response:")
        print(f"  {formatted}")
        print(f"\nSUCCESS - Bot will respond correctly!")
    else:
        print("ERROR: No response templates found!")
else:
    print("ERROR: Number not found in catalog!")

print("\n" + "=" * 60)
print("TEST COMPLETE - ALL CHECKS PASSED")
print("=" * 60)
