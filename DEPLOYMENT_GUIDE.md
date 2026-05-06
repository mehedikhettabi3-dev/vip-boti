# 🚀 دليل التصحيح والتخطيط (Deployment & Troubleshooting Guide)

## 📋 مشاكل تم حلها (Issues Fixed)

### ✅ 1. **السيت يوقف بعد البدية (Site Stops Working)**
**السبب:** 
- الـ keep-alive function كانت معتمدة على متغير `RENDER_EXTERNAL_URL` ما كاينش دائماً
- ما كاينش memory management للـ processed_messages
- الـ threading كاين بدون حد (threads explosion)

**الحل:**
- ✅ أضفنا `ThreadPoolExecutor` لتحديد عدد الخيوط (max 5 workers)
- ✅ غيرنا `processed_messages` من `set` لـ `OrderedDict` (LRU cache)
- ✅ تحسين `keep_alive()` مع logging أحسن
- ✅ إضافة session cleanup كل 50 دقيقة

### ✅ 2. **مشاكل الموثوقية**
- ✅ أضفنا timeout صحيح (15 ثانية للـ requests)
- ✅ معالجة أفضل للأخطاء مع logging تفصيلي
- ✅ `send_whatsapp_async()` - إرسال غير متزامن
- ✅ بناء graceful shutdown

---

## 🔧 إعدادات التكوين (Configuration)

### 1. **تحضير ملف `.env`**

```bash
# انسخ .env.example
cp .env.example .env

# ثم عدل القيم:
ACCESS_TOKEN=<token من Meta>
PHONE_NUMBER_ID=<رقم من Meta>
ADMIN_PHONE=212638388885
RENDER_EXTERNAL_URL=https://vip-boti.onrender.com
```

**الحصول على Meta Tokens:**
1. اذهب لـ [Meta Developers](https://developers.facebook.com)
2. اختر تطبيقك
3. Business App > WhatsApp > API Setup
4. انسخ **Permanent Access Token** و **Phone Number ID**

### 2. **التأكد من المتطلبات**
```bash
pip install -r requirements.txt
```

---

## 🏃 التشغيل المحلي (Local Testing)

### تشغيل مع Flask (للتطوير):
```bash
# في المجلد الرئيسي
python whatsapp_bot.py
```

سيعمل على: `http://localhost:10000`

### تشغيل مع Gunicorn (نفس Production):
```bash
# 4 workers مع 2 ثانية timeout
gunicorn -w 4 -b 0.0.0.0:10000 -t 120 wsgi:app
```

### اختبار الـ Webhook محلياً:
```bash
# استخدم ngrok للحصول على رابط عام
ngrok http 10000

# ستحصل على URL مثل: https://xxxx-xx-xxx.ngrok.io
# استخدمه في Meta Dashboard تحت Webhook URL
```

---

## 📱 إعدادات Meta WhatsApp

### 1. **إضافة Webhook في Meta Dashboard:**

الرابط: `https://your-app.onrender.com/webhook`

### 2. **Verify Token:**
استخدم: `vip_bot_2026` (أو غيّره في `api_keys.json`)

### 3. **Subscribe to Webhook Fields:**
✅ `messages` — لاستقبال الرسائل
✅ `message_status` — لحالة الرسائل

---

## 🐛 استكشاف الأخطاء (Troubleshooting)

### المشكلة: "Bot ما كيجاوب"

**الفحص الأول:**
```bash
# اطلب الـ health check
curl https://your-app.onrender.com/health
```

يجب ترى:
```json
{
  "status": "ok",
  "numbers_available": 5,
  "config": "✅"
}
```

**إذا كان الـ config `❌`:**
- Access Token غير صحيح
- Phone Number ID غير صحيح
- اتصل بـ Meta

### المشكلة: "الموقع يتوقف بعد ساعة"

**الحل:**
1. تأكد من الـ keep-alive active (يجب يبقى في الـ logs)
2. افحص الـ logs:
```bash
# من Render Dashboard أو:
curl https://your-app.onrender.com/logs --user admin:vip2026
```

3. إذا كانت الـ logs كتقول `[KEEP-ALIVE] Server ping timeout`:
   - قد يكون Render كتخفتش الـ server
   - شغّل `/health` endpoint يدويا

### المشكلة: "الأرقام ما كتتحدث في الـ catalog"

**الحل:**
1. افحص `catalog.json` — كاين فيه `status: "available"`؟
2. اصيفط لـ Bot: `!stats`
3. إذا كانت الأرقام `sold` بدون قصد:
   - صيفط: `!reset` — (مسح الجلسات)
   - حيّن `catalog.json` يدويا

---

## 📊 أوامر Admin من WhatsApp

صيفط من نمرتك (ADMIN_PHONE):

| الأمر | الفائدة |
|------|---------|
| `!stats` | إحصائيات الأرقام والطلبات |
| `!sold 0612345678` | تعليم رقم كمباع |
| `!add 0612345678 diamond 500` | إضافة رقم جديد |
| `!delete 0612345678` | حذف رقم |
| `!reset` | مسح الجلسات |
| `!test` | اختبار الإشعارات |
| `!help` | تذكير الأوامر |

---

## 📈 تحسينات للإنتاج (Production Best Practices)

### 1. **استخدام Gunicorn (بدل Flask):**
```bash
# في render.yaml:
build:
  command: pip install -r requirements.txt

start:
  command: gunicorn -w 4 -b 0.0.0.0:$PORT -t 120 wsgi:app
```

### 2. **مراقبة الـ Logs:**
- Render: Dashboard → Logs
- راقب `[KEEP-ALIVE]` entries كل 5 دقائق
- تأكد من ما فيه `ERROR` متكررة

### 3. **النسخ الاحتياطية (Backups):**
```bash
# اضغط على قيمة JSON files:
- catalog.json
- orders.json
- known_leads.json

# يومياً احتفظ بنسخة محفوظة!
```

### 4. **إضافة Monitoring (Optional):**
```bash
# Render Free Tier غير كافي، استخدم:
# - LogRocket (لـ frontend errors)
# - Sentry (لـ Python errors)
```

---

## ✨ الميزات المضافة (New Features)

### 1. **Thread Pool للـ WhatsApp Sending**
- معالجة أسرع للرسائل الكثيرة
- منع thread explosion
- تحديد max 5 workers

### 2. **Memory Management**
- `OrderedDict` بدل `set` (LRU cache)
- تنظيف تلقائي للـ sessions القديمة
- تحديد max 1000 message في الذاكرة

### 3. **Better Health Checks**
- `/health` endpoint يعطيك تفاصيل كاملة
- متتبعة الـ config status
- الإحصائيات الحية

### 4. **Graceful Shutdown**
- إغلاق نظيف للـ thread pool
- حفظ آخر البيانات قبل الإغلاق

---

## 🎯 التالي (Next Steps)

1. ✅ **حدّث الـ repository بالتغييرات الجديدة**
2. ✅ **Push على GitHub**
3. ✅ **Render سيعيد النشر تلقائياً**
4. ✅ **اختبر الـ Bot من WhatsApp**
5. ✅ **راقب الـ logs أول ساعة**

---

## 📞 للمساعدة

إذا كان في مشاكل:

1. افحص الـ health: `curl /health`
2. اقرا الـ logs: `curl /logs --user admin:vip2026`
3. اختبر الـ webhook: `POST /test` مع رسالة

**مبروك! البوت ديالك دابا مستقر وجاهز! 🎉**
