import json
import time
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================
# ⚙️ CONFIGURATION
# ============================================================
DB_FILE = "vip_numbers.json"
SESSION_DIR = "whatsapp_session"

# ============================================================
# 🎯 INTENT DETECTION (Moroccan Slang Sniper)
# ============================================================
def is_number_request(message):
    msg = message.lower().strip()
    
    # Regex Patterns
    nouns = r"\b(nm|nmr|nmra|nmera|num|numero|r9m|rqm|tel|wts|wtsp|wats|نمرة|رقم|واتساب|نمر)\b"
    verbs = r"\b(3tini|sift|passi|bghit|khasni|b4it|عطيني|صيفط|بغيت|خصني|ارسل|صيفطلي)\b"
    
    has_noun = re.search(nouns, msg)
    has_verb = re.search(verbs, msg)
    word_count = len(msg.split())
    
    # Logic: (Noun + Verb) OR (Noun AND short message)
    if (has_noun and has_verb) or (has_noun and word_count <= 3):
        return True
    return False

# ============================================================
# 📋 DATABASE LOADING
# ============================================================
def load_numbers():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# 🤖 BOT EXECUTION
# ============================================================
def run_bot():
    print("🚀 Initializing WhatsApp Sniper Bot...")
    
    # Selenium Setup
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={SESSION_DIR}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.get("https://web.whatsapp.com")
    print("⏳ Please scan the QR code if needed and wait for WhatsApp Web to load.")
    
    # Wait for the chat list to appear
    wait = WebDriverWait(driver, 60)
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, '//div[@id="pane-side"]')))
        print("✅ WhatsApp Web Loaded!")
    except:
        print("❌ Timeout waiting for WhatsApp Web. Retrying...")
        driver.get("https://web.whatsapp.com")

    numbers_db = load_numbers()
    
    try:
        while True:
            try:
                # 1. Look for unread chats (Green dot)
                unread_xpath = '//span[@aria-label="Unread"] | //span[contains(@aria-label, "unread")] | //span[contains(@class, "unread")]'
                unread_chats = driver.find_elements(By.XPATH, unread_xpath)
                
                if unread_chats:
                    print(f"🔔 Found {len(unread_chats)} unread chat(s).")
                    
                    for chat_indicator in unread_chats:
                        try:
                            # Click the chat element (parent of the unread indicator)
                            chat_element = chat_indicator.find_element(By.XPATH, './ancestor::div[@role="row"]')
                            chat_element.click()
                            time.sleep(2) # Human delay
                            
                            # 2. Get the last message
                            messages = driver.find_elements(By.XPATH, '//div[contains(@class, "message-in")]//span[contains(@class, "selectable-text")]')
                            if not messages:
                                continue
                                
                            last_msg_text = messages[-1].text
                            print(f"📩 Last message: {last_msg_text}")
                            
                            # 3. Check Intent
                            if is_number_request(last_msg_text):
                                print("🎯 Match! Formatting catalog...")
                                
                                # Format catalog from JSON
                                catalog_text = "Hado homa nwamr li b9aw, jawbni dghya 9bl maymchiw! ✨\n\n"
                                for num, price in numbers_db.items():
                                    formatted_num = f"{num[:2]} {num[2:4]} {num[4:6]} {num[6:8]} {num[8:]}"
                                    catalog_text += f"💎 {formatted_num} -> *{price}*\n"
                                
                                # 3.1 Find input box with robust XPath and explicit wait
                                try:
                                    # More flexible XPath that handles different WhatsApp Web versions
                                    input_xpath = '//div[@contenteditable="true"][@data-tab="10"] | //div[@title="Type a message"]'
                                    input_box = wait.until(EC.presence_of_element_located((By.XPATH, input_xpath)))
                                    input_box.clear()
                                    
                                    # Type message (correct syntax: Keys.SHIFT, Keys.ENTER as separate args)
                                    lines = catalog_text.split('\n')
                                    for i, line in enumerate(lines):
                                        input_box.send_keys(line)
                                        if i < len(lines) - 1:
                                            # الطريقة الصحيحة لـ Shift+Enter في سيلينيوم
                                            input_box.send_keys(Keys.SHIFT, Keys.ENTER)
                                    
                                    time.sleep(1) # Human delay
                                    input_box.send_keys(Keys.ENTER) # Send message
                                    print("✅ Catalog sent.")
                                except Exception as input_err:
                                    print(f"⚠️ Could not find or use input box: {input_err}")
                                
                        except Exception as e:
                            print(f"⚠️ Error processing individual chat: {e}")
                            continue
                
                # 4. Anti-Ban Delay
                time.sleep(3)
                
            except Exception as e:
                print(f"💥 Critical Loop Error: {e}")
                time.sleep(5) # Wait and retry
    finally:
        print("👋 Shutting down bot...")
        driver.quit()

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
