import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "app" in sys.modules: del sys.modules["app"]
import importlib, app; importlib.reload(app)

tests = [
    ("T14", "r9m 07 20 86 88 88 bch7l", ["0720868888"], []),
    ("T21", "kayn chi nmra dial méditel", ["Orange", "Inwi"], []),
    ("T23", "je veux un numéro maroc telecom VIP", ["Maroc"], []),
    ("T27", "kayn chi nmra b 50 dh", ["100", "150"], ["50"]),
    ("T44", "bghit 10 nwamer b souh ljomla", ["رقم"], []),
    ("T49", "kifach kate3ml l'activation d nmra", ["تسجيل", "تفعيل"], []),
    ("T50", "wach 3ndkom garantie", ["ثقة"], []),
    ("T68", "لا", ["لا يوجد"], []),
    ("T93", "https://example.com/vip-numbers", ["مرحبا"], []),
]

for name, inp, expected, not_exp in tests:
    app.user_states.clear()
    sender = "212600000001"
    if name == "T68":
        app.user_states[sender] = {"step": 3, "data": {"vip_number": "0661123456", "name": "H", "city": "T"}}
    reply = app.handle_logic(sender, inp) or ""
    ok = all(k in reply for k in expected) and all(k not in reply for k in not_exp)
    print(f'{"[OK]" if ok else "[FAIL]"} {name}: {inp[:50]}')
    if not ok:
        print(f"  Reply: {repr(reply[:200])}")
        for k in expected:
            if k not in reply: print(f"  MISSING: {k}")
        for k in not_exp:
            if k in reply: print(f"  UNEXPECTED: {k}")
