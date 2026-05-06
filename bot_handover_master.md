# 👑 VIP Number Project - Master Handover (A to Z)

## 1. Project Overview
A premium Moroccan marketplace for VIP Inwi phone numbers with an automated WhatsApp sales bot.

---

## 2. Key Contacts & IDs
- **Official Bot Number (WhatsApp)**: `212638388885` (All site buttons point here).
- **Admin Phone Number**: `212625489153` (Authorized to use bot commands).
- **Meta App IDs (from api_keys.json)**:
  - `PHONE_NUMBER_ID`: `1005738575965416`
  - `WABA_ID`: `1281821344074761`
  - `ACCESS_TOKEN`: `EAARvYecnWT4BRfF03TaW7puQMi948ZBi3HboTdpOIsZBZAc997ZAOw0B5H5cT0YuhHEmD03H4ibXFRHvEkUXGTeaB20zuyDpd3MhDaLXbfLbJLipv55AVSgO2oSZCQ330B1c41SNxfRf0dyxWoNNmf8YhWo14ZAg5kZCyhDyx6cN4QQYfFYeOurUI9LXW3l`

---

## 3. File Architecture
- **`vip_numbers.json`**: The master inventory file (26 numbers).
- **`bot.py`**: The main automation engine using Selenium.
- **`src/App.tsx`**: The React frontend (UI and catalog logic).
- **`src/index.css`**: Luxury styling tokens (Zellige, Wings, Animations).
- **`api_keys.json`**: Secure storage for all API credentials.

---

## 4. Bot Logic (bot.py)
- **Engine**: Selenium + Chrome WebDriver.
- **Session**: Saved in `whatsapp_session/` (No QR rescan needed).
- **Intent Detection**: Uses Regex to catch Moroccan slang (`nm`, `3tini`, `bghit`, etc.).
- **Admin Commands**:
  - `/add [number] [price]`
  - `/del [number]`
  - `/list`

---

## 5. Frontend Logic (App.tsx)
- **Fallback Catalog**: Hardcoded numbers in `App.tsx` serve as a safety net.
- **Protected Merge**: `mergeWithProtectedCatalog` ensures that even if the API sends old data, the correct inventory is prioritized.
- **WhatsApp Link Generation**: `https://wa.me/212638388885?text=...`

---

## 6. Deployment Workflow (CRITICAL)
1. **Local Build**: Run `npm run build` to generate the `dist/` folder.
2. **Sync**: Push changes to GitHub.
3. **Render**: Use "Clear Cache and Deploy" on the Render Dashboard to ensure the latest code and numbers are live.

---

## 8. Design System (Royal Aesthetics)
- **Primary Purple**: `#A855F7` (Fuchsia/Purple)
- **Primary Gold**: `#FBBF24` (Amber/Yellow)
- **Background**: `#030201` (Deep Black)
- **Animations**: 
  - `welcome-bot-wave`: 1.4s loop.
  - `winged-card`: Hover-triggered 3D transformation.
  - `zellige-luxury`: 20s linear drift.

## 9. Regex Sniper Logic (Deep Dive)
- **Nouns Pattern**: `r"\b(nm|nmr|nmera|num|numero|r9m|tel|wts|نمرة|رقم|واتساب)\b"`
  - `\b` ensures we catch "nm" but NOT "name".
- **Verbs Pattern**: `r"\b(3tini|sift|passi|bghit|khasni|عطيني|صيفط|بغيت)\b"`
- **Trigger Condition**: `(Noun + Verb)` OR `(Noun + WordCount <= 3)`.

## 10. Dependency List
- **Python (requirements.txt)**:
  - `selenium` (Browser automation)
  - `webdriver-manager` (Driver management)
  - `requests` (API calls)
  - `flask` (For webhook server)
- **Frontend (package.json)**:
  - `framer-motion` (Animations)
  - `lucide-react` (Icons)
  - `tailwindcss` (Styling)
  - `vite` (Build tool)

## 11. Server & API URLs
- **Main API**: `https://vip-boti.onrender.com/api/full_catalog`
- **Webhook Endpoint**: `https://vip-boti.onrender.com/webhook`
- **Render Dashboard**: Check logs for any "Connection Refused" errors.

## 12. Troubleshooting & Maintenance
- **Token Expiry**: If Cloud API fails, check `api_keys.json` and generate a new token in the Meta Developer Portal.
- **Bot Slowdown**: If Selenium is slow, increase `time.sleep()` values in `bot.py`.
- **Site Update**: Always run `npm run build` before pushing to ensure the `dist/` bundle is fresh.
