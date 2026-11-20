"""Emoji yordamchilari.

Oddiy emoji har doim ishlaydi. Premium (custom) emoji ID'larini bersangiz, tugmalarda ikonka,
matnda <tg-emoji> ko'rinadi. ID'lar Web App admin paneldan kiritiladi (bazada saqlanadi).
Qo'shimcha manbalar: EMOJI_IDS muhit o'zgaruvchisi (JSON) yoki emoji_ids.json fayli.
Ustunlik tartibi: fayl < muhit < baza (panel).
"""
import json
import os
import sqlite3

from dbpath import DB_PATH

HERE = os.path.dirname(os.path.abspath(__file__))

# (kalit, nomi, guruh, oddiy emoji) — TARTIB muhim: panelda "tartib bo'yicha joylash" shu ketma-ketlikda
_META = [
    ("battle", "Battle yaratish", "Asosiy menyu", "⚔️"),
    ("contest", "Konkurs yaratish", "Asosiy menyu", "🏆"),
    ("my_battles", "Mening battlelarim", "Asosiy menyu", "📋"),
    ("my_contests", "Mening konkurslarim", "Asosiy menyu", "🗂"),
    ("profile", "Profil", "Asosiy menyu", "👤"),
    ("lang", "Til", "Asosiy menyu", "🌐"),
    ("support", "Yordam", "Asosiy menyu", "💬"),
    ("guide", "Qo'llanma", "Asosiy menyu", "📖"),
    ("menu", "Menyu", "Asosiy menyu", "📋"),
    ("quiz", "Savol (viktorina)", "Bonus menyu", "❓"),
    ("daily", "Kunlik bonus", "Bonus menyu", "🎁"),
    ("shop", "Magazin", "Bonus menyu", "🛒"),
    ("promo", "Promokod", "Bonus menyu", "🎟"),
    ("share", "Ulashish", "Bonus menyu", "🔗"),
    ("home", "Uy (bosh menyu)", "Bonus menyu", "🏠"),
    ("coin", "Coin (ball)", "Bonus menyu", "🪙"),
    ("gift", "Sovg'a", "Bonus menyu", "🎁"),
    ("bend", "Battle tugatish", "Battle va konkurs tugmalari", "🏁"),
    ("bjoin", "Qatnashish", "Battle va konkurs tugmalari", "🙋"),
    ("boost", "Boost", "Battle va konkurs tugmalari", "🚀"),
    ("boostchk", "Boost tekshirilmoqda", "Battle va konkurs tugmalari", "🔎"),
    ("bres", "Natijalar (statistika)", "Battle va konkurs tugmalari", "📊"),
    ("bvot", "Ovoz berganlar", "Battle va konkurs tugmalari", "🗳"),
    ("cancel", "Rad etildi", "Battle va konkurs tugmalari", "❌"),
    ("cend", "Konkurs tugatish", "Battle va konkurs tugmalari", "🏁"),
    ("check", "Tasdiqlandi (tekshirish)", "Battle va konkurs tugmalari", "✅"),
    ("device", "Qurilmani tasdiqlash", "Battle va konkurs tugmalari", "📱"),
    ("w_party", "Xush kelibsiz: bayram", "Xabar belgilari", "🎉"),
    ("w_pin", "Xush kelibsiz: eslatma", "Xabar belgilari", "📌"),
    ("w_mega", "Kanallar", "Xabar belgilari", "📣"),
    ("w_gold", "1-o'rin", "Xabar belgilari", "🥇"),
    ("w_silver", "2-o'rin", "Xabar belgilari", "🥈"),
    ("w_bronze", "3-o'rin", "Xabar belgilari", "🥉"),
    ("w_ok", "Tasdiqlandi", "Xabar belgilari", "✅"),
    ("w_people", "Foydalanuvchilar", "Xabar belgilari", "👥"),
    ("w_warn", "Ogohlantirish", "Xabar belgilari", "⚠️"),
    ("w_down", "Pastga", "Xabar belgilari", "👇"),
    ("w_back", "Orqaga", "Xabar belgilari", "👈"),
]
ORDER = [m[0] for m in _META]
FALLBACK = {m[0]: m[3] for m in _META}


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS emoji_ids(key TEXT PRIMARY KEY, id TEXT)")
    return c


def _load_ids() -> dict:
    data = {}
    path = os.path.join(HERE, "emoji_ids.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data.update(json.load(f))
        except Exception:
            pass
    raw = os.getenv("EMOJI_IDS", "").strip()
    if raw:
        try:
            data.update(json.loads(raw))
        except Exception:
            pass
    try:
        c = _conn()
        for k, v in c.execute("SELECT key, id FROM emoji_ids"):
            data[k] = v          # bo'sh qiymat = panelda tozalangan
        c.commit()
        c.close()
    except Exception:
        pass
    return {k: str(v) for k, v in data.items() if v}


IDS = _load_ids()


def save_ids(mapping: dict) -> None:
    """{kalit: id yoki ''} ni bazaga yozadi va xotirani yangilaydi. Noma'lum kalitlar e'tiborsiz."""
    c = _conn()
    for k, v in mapping.items():
        if k not in FALLBACK:
            continue
        v = str(v or "").strip()
        c.execute("INSERT OR REPLACE INTO emoji_ids(key,id) VALUES(?,?)", (k, v))
        if v:
            IDS[k] = v
        else:
            IDS.pop(k, None)
    c.commit()
    c.close()


def items() -> list:
    return [{"n": i, "key": k, "label": lbl, "group": grp, "fallback": fb, "id": IDS.get(k, "")}
            for i, (k, lbl, grp, fb) in enumerate(_META, 1)]


def pid(key: str):
    """Premium emoji ID yoki None."""
    return IDS.get(key)


def label(key: str, text: str) -> str:
    """Tugma matni: premium ID bo'lsa ikonka alohida chiqadi (matn toza),
    bo'lmasa oddiy emoji matn oldiga qo'shiladi."""
    if pid(key):
        return text
    return f"{FALLBACK.get(key, '')} {text}".strip()


def tg(key: str) -> str:
    """Xabar matni uchun emoji (HTML parse_mode)."""
    fb = FALLBACK.get(key, "•")
    i = pid(key)
    return f'<tg-emoji emoji-id="{i}">{fb}</tg-emoji>' if i else fb
