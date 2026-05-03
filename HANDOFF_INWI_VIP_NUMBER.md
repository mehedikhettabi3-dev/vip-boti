# Inwi VIP Number — Complete Handoff File

Use this file to give Claude, a developer, Netlify, or Render everything needed to recreate/deploy the site.

---

## 1) Project Summary

Build a premium mobile-first landing page for **Inwi VIP Number**.

Tech stack:
- Vite
- React
- TypeScript
- Tailwind CSS
- Framer Motion
- Lucide React

Design style:
- Dark luxury theme
- Purple, black, and gold colors
- Mobile-first for TikTok traffic
- 3D background that does not block content
- Floating phone/SIM shapes
- Robot face with eyes following mouse movement
- WhatsApp order buttons
- Sales popup every 5 seconds

Important behavior:
- Number cards must never disappear.
- Show backup catalog immediately.
- Fetch live API in the background.
- If API is slow/fails, keep backup catalog visible.

---

## 2) Live API

Fetch catalog from:

```txt
https://vip-boti.onrender.com/api/full_catalog
```

Expected API format:

```json
{
  "Diamond": [
    { "number": "07 03 31 33 13", "price": "200 DH", "status": "available", "tier": "Diamond" }
  ],
  "Gold": [],
  "Inwi": [],
  "Silver": []
}
```

---

## 3) WhatsApp Link Format

Every number button must link to:

```txt
https://wa.me/212778375026?text=NUMBER_HERE
```

Example:

```txt
https://wa.me/212778375026?text=07%2003%2031%2033%2013
```

In code:

```ts
const WHATSAPP_BASE = 'https://wa.me/212778375026?text='
const getWhatsAppUrl = (number: string) => `${WHATSAPP_BASE}${encodeURIComponent(number)}`
```

---

## 4) Exact Backup Catalog

Use this backup catalog immediately so cards never disappear.

### Diamond

```txt
07 03 31 33 13 — 200 DH
06 38 38 88 85 — 200 DH
07 17 47 44 47 — 200 DH
06 05 55 51 18 — 200 DH
07 07 23 60 61 — 200 DH
```

### Gold

```txt
06 09 39 01 07 — 200 DH
07 06 06 36 79 — 100 DH
06 04 03 89 84 — 100 DH
07 05 05 76 81 — 100 DH
07 03 22 06 00 — 100 DH
06 06 09 03 48 — 200 DH
06 07 03 13 11 — 100 DH
07 24 01 23 01 — 100 DH
07 05 11 19 13 — 100 DH
07 20 05 07 44 — 100 DH
07 05 70 74 08 — 100 DH
06 02 44 01 11 — 100 DH
06 35 38 28 35 — 100 DH
06 99 46 46 49 — 100 DH
07 10 14 44 48 — 100 DH
07 05 07 06 71 — 200 DH
```

### Inwi

```txt
06 99 99 34 38 — 200 DH
07 11 11 67 33 — 200 DH
07 06 88 88 18 — 150 DH
07 06 03 33 03 — 150 DH
06 06 96 06 07 — 150 DH
07 13 33 37 06 — 150 DH
07 25 37 77 70 — 150 DH
07 04 46 66 61 — 150 DH
06 08 78 88 82 — 150 DH
07 22 20 23 10 — 150 DH
07 25 24 22 29 — 150 DH
06 04 05 05 59 — 150 DH
06 09 91 96 27 — 100 DH
07 05 77 97 77 — 100 DH
06 99 22 90 94 — 100 DH
07 00 67 08 07 — 100 DH
07 00 50 04 53 — 150 DH
07 25 02 22 28 — 150 DH
07 03 85 04 03 — 150 DH
06 06 78 09 57 — 150 DH
07 04 05 54 59 — 150 DH
```

### Silver

```txt
06 33 37 42 84 — 100 DH
07 03 33 81 35 — 100 DH
07 20 43 20 59 — 100 DH
07 16 34 94 44 — 100 DH
07 25 88 33 03 — 100 DH
```

Total numbers: **47**

---

## 5) Prompt To Give Claude / Developer

Copy and paste this:

```txt
Create a Vite + React + TypeScript + Tailwind landing page called "Inwi VIP Number".

The site must be mobile-first because traffic will come from TikTok. Use a luxury dark theme with purple, black, and gold colors.

Features:
1. Hero section with brand name "Inwi VIP Number".
2. Hero number: 07 03 31 33 13.
3. WhatsApp buttons must use this exact format:
   https://wa.me/212778375026?text= followed by the selected number.
4. Fetch live catalog from:
   https://vip-boti.onrender.com/api/full_catalog
5. Use backup catalog immediately so numbers never disappear.
6. Sync the API in the background.
7. If API fails or sleeps, keep backup catalog visible.
8. Categorize numbers by: Diamond, Gold, Inwi, Silver.
9. Every card must show number, tier, price, and "Order via WhatsApp" button.
10. Add subtle safe 3D background: floating phone shapes, SIM chip, luxury purple/gold grid.
11. Add a robot face with eyes following the mouse.
12. Add a glassmorphism sales popup every 5 seconds showing a Moroccan name/city and random number/price.
13. Do not let animations hide cards.
14. Make it responsive and fast on phones.
15. Build must pass with npm run build.

Use the full backup catalog listed in this handoff file.
```

---

## 6) Install & Run Locally

```bash
npm install
npm run dev
```

Build:

```bash
npm run build
```

Preview production build:

```bash
npm run preview
```

---

## 7) Netlify Deployment

Netlify settings:

```txt
Build command: npm run build
Publish directory: dist
```

Optional `netlify.toml`:

```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

Steps:
1. Push project to GitHub.
2. Go to Netlify.
3. Add new site → Import from Git.
4. Select repository.
5. Use build command `npm run build`.
6. Use publish directory `dist`.
7. Deploy.

---

## 8) Render Deployment

Render Static Site settings:

```txt
Build command: npm install && npm run build
Publish directory: dist
```

Optional `render.yaml`:

```yaml
services:
  - type: web
    name: inwi-vip-number
    env: static
    buildCommand: npm install && npm run build
    staticPublishPath: dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

Steps:
1. Push project to GitHub.
2. Go to Render.
3. New → Static Site.
4. Select repository.
5. Build command: `npm install && npm run build`.
6. Publish directory: `dist`.
7. Deploy.

---

## 9) Files That Matter

Main files:

```txt
src/App.tsx       → full page logic/design
src/index.css     → global CSS + 3D background animations
index.html        → title/favicon
public/favicon.svg
```

Dependencies needed:

```json
{
  "@tailwindcss/vite": "latest",
  "framer-motion": "latest",
  "lucide-react": "latest",
  "react": "latest",
  "react-dom": "latest",
  "tailwindcss": "latest",
  "vite": "latest",
  "typescript": "latest"
}
```

---

## 10) Quality Checklist

Before deploying, check:

- [ ] `npm run build` passes.
- [ ] 47 backup numbers exist.
- [ ] Cards visible before API loads.
- [ ] API loads in background.
- [ ] WhatsApp links use `https://wa.me/212778375026?text=`.
- [ ] Hero number is `07 03 31 33 13`.
- [ ] Mobile layout works.
- [ ] 3D background does not cover buttons/cards.
- [ ] Robot eyes move with mouse.
- [ ] TikTok/mobile traffic can read and click easily.

---

## 11) Notes In Darija

Had l-file 3tih l Claude ola developer:

```txt
Bghit site b7al hada: Inwi VIP Number. Dir Vite React TypeScript Tailwind. Khlli numbers ybano dima, API ila t3tlat maym7awch cards. WhatsApp links khasom ykono https://wa.me/212778375026?text= + number. Theme purple black gold, mobile-first 7it traffic mn TikTok. Zid 3D background safe, robot eyes kayt7rko m3a mouse, popup dyal sales kol 5 seconds.
```
