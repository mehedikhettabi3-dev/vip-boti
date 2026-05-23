from core.database import get_users_by_status, get_recent_buyers, save_message
from services.whatsapp_sender import WhatsAppAPI


async def fomo_retargeting():
    try:
        phones = await get_users_by_status("new", min_days_old=3)
        for phone in phones:
            try:
                msg = (
                    "السلام عليكم سيدي. 😊 هذا أنا المسؤول عن مبيعات الأرقام VIP. "
                    "عندي خبر مهم: الرقم اللي كنت سائل عليه باقي نسخة وحيدة في المخزن فقط! ⏳ "
                    "كليان آخر دابا قال لي حاب يحجزو. إيلا ما حجزتيهش دابا ب 135 درهم، "
                    "غادي نحجزوه للكليان الآخر. واش تحجزو ولا نحجزو للكليان الآخر؟ 🤝"
                )
                WhatsAppAPI.send_text(phone, msg)
                await save_message(phone, "bot", msg)
                print(f"[Retarget] FOMO sent to {phone}")
            except Exception as e:
                print(f"[Retarget] Error for {phone}: {e}")
    except Exception as e:
        print(f"[Retarget] fomo_retargeting error: {e}")


async def auto_referral():
    try:
        phones = await get_recent_buyers(hours_ago=24)
        import random
        for phone in phones:
            try:
                code = f"VIP{random.randint(1000, 9999)}"
                msg = (
                    f"بصحتك سيدي! 🎉 لقد حجزت رقم VIP ممتاز! هذا هو كود الإحالة الخاص بك: {code}\n\n"
                    "كيفاش تجيب صاحبك:\n"
                    "1. قولو يحجز رقم VIP عندنا\n"
                    "2. يكتب الكود {code} في رسالته\n"
                    "3. هو غادي يستفيد من 20 درهماً تخفيض، وأنت غادي تستفيد من 20 درهماً رصيد!\n\n"
                    "واش حاب تجرب هاد العرض؟ ✨"
                )
                WhatsAppAPI.send_text(phone, msg)
                await save_message(phone, "bot", msg)
                print(f"[Referral] Code {code} sent to {phone}")
            except Exception as e:
                print(f"[Referral] Error for {phone}: {e}")
    except Exception as e:
        print(f"[Referral] auto_referral error: {e}")
