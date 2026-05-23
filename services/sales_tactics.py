import re
from core.database import update_lead_score, update_user_city

MOROCCAN_CITIES = [
    "casablanca", "rabat", "marrakech", "fes", "tanger", "agadir",
    "meknes", "oujda", "kenitra", "tetouan", "safi", "el jadida",
    "beni mellal", "nador", "taza", "settat", "laayoune", "dakhla",
    "ksar el kebir", "sale", "temara", "mohammedia", "khouribga",
    "berrechid", "taourirt", "sidi kacem", "larache", "tangier",
    "youssoufia", "guercif", "fquih ben salah", "oued zem", "midelt",
    "azrou", "tiflet", "benslimane", "skhirat", "bin el ouidane",
]


def extract_city(text):
    try:
        lower = text.lower()
        for city in MOROCCAN_CITIES:
            if city in lower:
                return city.capitalize()
        patterns = [
            r"mn\s+(\w+)", r"f\s+(\w+)", r"dial\s+(\w+)",
            r"ana\s+mn\s+(\w+)", r"ani\s+f\s+(\w+)", r"ساكن\s+(\w+)",
            r"من\s+(\w+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                candidate = match.group(1).capitalize()
                if candidate.lower() in MOROCCAN_CITIES:
                    return candidate
        return None
    except Exception:
        return None


def calculate_lead_score(text):
    try:
        score = 0
        lower = text.lower()
        greetings = ["salam", "salamo", "bonjour", "hi", "hello", "marhaba"]
        interest = ["catalog", "catalogue", "numbers", "ar9am", "ra9m", "ch7al", "prix", "kam", "price"]
        buying_signals = [
            "kifach nkheles", "kayfa nkheles", "paiement", "pay", "kifach",
            "bghit nchri", "bghit n7ejes", "7ejes", "chrit", "شراء",
            "دفع", "كيفاش", "bghit", "n7ejes",
        ]
        for word in greetings:
            if word in lower:
                score += 1
                break
        for word in interest:
            if word in lower:
                score += 5
                break
        for phrase in buying_signals:
            if phrase in lower:
                score += 10
                break
        if "ghali" in lower or "too expensive" in lower or "bzf" in lower or "غالي" in lower:
            score += 3
        if any(str(d) in lower for d in ["115", "135", "250"]):
            score += 4
        return score
    except Exception:
        return 0


def analyze_message(phone_number, text):
    try:
        city = extract_city(text)
        if city:
            update_user_city(phone_number, city)
        score_delta = calculate_lead_score(text)
        if score_delta > 0:
            update_lead_score(phone_number, score_delta)
        return {"city": city, "score_delta": score_delta}
    except Exception:
        return {"city": None, "score_delta": 0}
