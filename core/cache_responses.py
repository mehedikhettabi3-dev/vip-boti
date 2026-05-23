CACHED_RESPONSES = {
    "salam": 'السلام عليكم سيدي! كيفاش نقدر نعاونك في الأرقام VIP اليوم؟ عندنا تشكيلة ممتازة من Gold و Silver و Diamond! 📱✨',
    "salam 3likom": 'وعليكم السلام سيدي! 🌟 واش حاب تشوف الكاتالوك ديال الأرقام VIP اللي عندنا؟ عندنا فئات مختلفة: VIP و Diamond و Gold و Silver.',
    "salam alikom": 'وعليكم السلام سيدي! 🌟 واش حاب تشوف الكاتالوك ديال الأرقام VIP اللي عندنا؟ عندنا فئات مختلفة: VIP و Diamond و Gold و Silver.',
    "hi": 'السلام عليكم سيدي! ⭐ واش حاب تتصفح التشكيلة الحصرية ديالنا أرقام VIP بأسعار مغرية؟',
    "hello": 'السلام عليكم سيدي! ⭐ واش حاب تتصفح التشكيلة الحصرية ديالنا أرقام VIP بأسعار مغرية؟',
    "bonjour": 'السلام عليكم سيدي! 🌟 Vous cherchez des numéros VIP exceptionnels? Nous avons une sélection exclusive pour vous!',
    "prix": 'السلام عليكم سيدي. الأسعار عندنا كالتالي: 🔹 VIP (250 درهم) 🔹 Diamond (150 درهم بدل 200 - بروموسيون) 🔹 Gold (150 درهم) 🔹 Silver (100 درهم). واش حاب تعرف أكثر على فئة معينة؟',
    "catalog": 'السلام عليكم سيدي. هذه هي الفئات المتوفرة عندنا:\n\n💎 VIP - 250 DH\n⭐ Diamond - 150 DH (عوض 200)\n👑 Gold - 150 DH\n🔹 Silver - 100 DH\n\nواش حاب تختار فئة باش نعطيك التفاصيل؟ ✨',
    "thank you": 'العفو سيدي! 😊 دايماً في خدمتك. إيلا محتاج أي مساعدة، أنا هنا.',
    "merci": 'العفو سيدي! 😊 دايماً في خدمتك. إيلا محتاج أي مساعدة، أنا هنا.',
    "shokran": 'العفو سيدي! 😊 دايماً في خدمتك. إيلا محتاج أي مساعدة، أنا هنا.',
    "bye": 'في أمان الله سيدي! 🌟 نتمنى نسمع منك قريباً إن شاء الله.',
    "bslama": 'في أمان الله سيدي! 🌟 نتمنى نسمع منك قريباً إن شاء الله.',
    "السلام عليكم": 'وعليكم السلام ورحمة الله سيدي! 🌟 كيفاش نقدر نعاونك اليوم في اختيار رقم VIP مميز؟',
}


def get_cached_response(text):
    try:
        clean = text.strip().lower()
        if clean in CACHED_RESPONSES:
            return CACHED_RESPONSES[clean]
        for key, reply in CACHED_RESPONSES.items():
            if key in clean:
                return reply
        return None
    except Exception:
        return None
