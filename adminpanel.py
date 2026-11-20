"""Web App admin panel: faqat adminlar uchun (Telegram initData imzosi + ADMIN ro'yxati)."""
import asyncio
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

import emojis
import webapp

HERE = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("adminpanel")
UZ = timezone(timedelta(hours=5))


class ApiError(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.msg, self.status = msg, status


def _restart_process():
    log.warning("Bot qayta ishga tushirilmoqda (admin panel buyrug'i)...")
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os.execv(sys.executable, [sys.executable] + sys.argv)


def setup(app: web.Application, bot, token: str, *, db, admin_ids: set, env_admins: set,
          connected_channels, req_channels):
    """admin_ids — bot bilan umumiy set (o'zgartirilsa, bot ham darhol ko'radi)."""

    def one(sql, *args):
        return db.execute(sql, args).fetchone()[0]

    def api(fn):
        async def handler(request: web.Request):
            user = webapp.check_init_data(request.headers.get("X-Init-Data", ""), token)
            if not user or user.get("id") not in admin_ids:
                return web.json_response({"ok": False, "error": "forbidden"}, status=403)
            try:
                body = await request.json() if request.can_read_body else {}
            except Exception:
                body = {}
            try:
                res = await fn(user, body if isinstance(body, dict) else {})
            except ApiError as e:
                return web.json_response({"ok": False, "error": e.msg}, status=e.status)
            except Exception:
                log.exception("admin API xatosi: %s", fn.__name__)
                return web.json_response({"ok": False, "error": "server"}, status=500)
            return web.json_response({"ok": True, **res})
        return handler

    # ---------- sahifa ----------
    async def page(_):
        with open(os.path.join(HERE, "admin.html"), encoding="utf-8") as f:
            html = f.read()
        return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-store"})

    # ---------- me / statistika ----------
    async def me(user, body):
        name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or "Admin"
        return {"id": user["id"], "name": name, "owner": user["id"] in env_admins}

    async def stats(user, body):
        today = datetime.now(UZ).date()
        week = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            week.append({"day": d.isoformat(), "wd": d.weekday(),
                         "n": one("SELECT COUNT(*) FROM users WHERE joined=?", d.isoformat())})
        return {
            "users": one("SELECT COUNT(*) FROM users"),
            "today": one("SELECT COUNT(*) FROM users WHERE joined=?", today.isoformat()),
            "banned": one("SELECT COUNT(*) FROM users WHERE banned=1"),
            "points": one("SELECT COALESCE(SUM(points),0) FROM users"),
            "battles": one("SELECT COUNT(*) FROM battles"),
            "battles_active": one("SELECT COUNT(*) FROM battles WHERE status='active'"),
            "contests": one("SELECT COUNT(*) FROM contests"),
            "contests_active": one("SELECT COUNT(*) FROM contests WHERE status='active'"),
            "channels": len(connected_channels()),
            "req_channels": len(req_channels()),
            "admins": len(admin_ids),
            "emoji_set": len(emojis.IDS),
            "emoji_total": len(emojis.ORDER),
            "week": week,
        }

    # ---------- adminlar ----------
    def admin_rows():
        names = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM admins")}
        rows = []
        for uid in sorted(admin_ids, key=lambda x: (x not in env_admins, x)):
            u = db.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
            rows.append({"id": uid, "name": names.get(uid) or (u["name"] if u else "") or "—",
                         "owner": uid in env_admins})
        return rows

    async def admins(user, body):
        return {"admins": admin_rows()}

    async def admins_add(user, body):
        raw = str(body.get("id", "")).strip()
        if not re.fullmatch(r"\d{5,15}", raw):
            raise ApiError("ID faqat raqamlardan iborat bo'lishi kerak (5–15 xona).")
        uid = int(raw)
        if uid in admin_ids:
            raise ApiError("Bu foydalanuvchi allaqachon admin.")
        name = ""
        try:
            ch = await bot.get_chat(uid)
            name = " ".join(x for x in (ch.first_name, ch.last_name) if x) or (ch.title or "")
        except Exception:
            u = db.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
            name = u["name"] if u else ""
        db.execute("INSERT OR REPLACE INTO admins(id,name,added_by,added) VALUES(?,?,?,?)",
                   (uid, name, user["id"], datetime.now(UZ).strftime("%Y-%m-%d")))
        db.commit()
        admin_ids.add(uid)
        notified = True
        try:
            await bot.send_message(uid, "🎉 Siz bot administratori qilindingiz.\n/admin buyrug'i bilan panelni oching.")
        except Exception:
            notified = False     # foydalanuvchi botga hali /start bosmagan
        return {"admins": admin_rows(), "notified": notified}

    async def admins_remove(user, body):
        try:
            uid = int(body.get("id"))
        except (TypeError, ValueError):
            raise ApiError("ID noto'g'ri.")
        if uid in env_admins:
            raise ApiError("Asosiy adminni (ADMIN_IDS) panel orqali o'chirib bo'lmaydi.")
        if uid == user["id"]:
            raise ApiError("O'zingizni o'chira olmaysiz.")
        if uid not in admin_ids:
            raise ApiError("Bunday admin topilmadi.", 404)
        db.execute("DELETE FROM admins WHERE id=?", (uid,))
        db.commit()
        admin_ids.discard(uid)
        return {"admins": admin_rows()}

    # ---------- premium emoji ----------
    async def emoji_list(user, body):
        return {"items": emojis.items(), "set": len(emojis.IDS)}

    async def emoji_save(user, body):
        raw = body.get("items")
        if not isinstance(raw, dict) or not raw:
            raise ApiError("Saqlash uchun o'zgarish yo'q.")
        clean, bad_format = {}, []
        for k, v in raw.items():
            if k not in emojis.FALLBACK:
                continue
            v = str(v or "").strip()
            if v and not re.fullmatch(r"\d{5,25}", v):
                bad_format.append(k)
                continue
            clean[k] = v
        verified, invalid, checked = {}, [], True
        ids = sorted({v for v in clean.values() if v})
        if ids:
            try:
                found = {}
                for i in range(0, len(ids), 100):
                    for s in await bot.get_custom_emoji_stickers(custom_emoji_ids=ids[i:i + 100]):
                        found[s.custom_emoji_id] = s.emoji or ""
                for k, v in list(clean.items()):
                    if not v:
                        continue
                    if v in found:
                        verified[k] = found[v]
                    else:
                        invalid.append(k)
                        clean.pop(k)
            except Exception:
                log.exception("emoji ID'larni Telegram orqali tekshirib bo'lmadi")
                checked = False   # tarmoq xatosi: tekshirmasdan saqlaymiz
        emojis.save_ids(clean)
        return {"items": emojis.items(), "set": len(emojis.IDS), "saved": len(clean),
                "invalid": invalid + bad_format, "verified": verified, "checked": checked}

    async def restart(user, body):
        asyncio.get_running_loop().call_later(1.2, _restart_process)
        return {}

    # ---------- foydalanuvchilar ----------
    async def users_search(user, body):
        q, sort = str(body.get("q", "")).strip(), body.get("sort", "new")
        where, args = "1=1", []
        if q.isdigit():
            where, args = "id=?", [int(q)]
        elif q:
            where, args = "name LIKE ?", [f"%{q}%"]
        if sort == "ban":
            where += " AND banned=1"
        order = "points DESC" if sort == "top" else "rowid DESC"
        rows = db.execute(f"SELECT id,name,points,joined,banned FROM users WHERE {where} ORDER BY {order} LIMIT 40", args).fetchall()
        return {"users": [dict(r) for r in rows]}

    def user_row(uid):
        r = db.execute("SELECT id,name,points,joined,banned FROM users WHERE id=?", (uid,)).fetchone()
        if not r:
            raise ApiError("Foydalanuvchi topilmadi.", 404)
        return dict(r)

    async def users_ban(user, body):
        uid = int(body.get("id", 0))
        user_row(uid)
        if uid in admin_ids:
            raise ApiError("Adminni bloklab bo'lmaydi.")
        db.execute("UPDATE users SET banned=? WHERE id=?", (1 if body.get("ban") else 0, uid))
        db.commit()
        return {"user": user_row(uid)}

    async def users_points(user, body):
        uid, delta = int(body.get("id", 0)), int(body.get("delta", 0))
        user_row(uid)
        if not delta or abs(delta) > 1_000_000:
            raise ApiError("Ball noto'g'ri.")
        db.execute("UPDATE users SET points=MAX(0,points+?) WHERE id=?", (delta, uid))
        db.commit()
        return {"user": user_row(uid)}

    # ---------- xabar yuborish ----------
    jobs, running = {}, set()

    async def bc_start(user, body):
        text, target = str(body.get("text", "")).strip(), body.get("target")
        if not text or len(text) > 4000:
            raise ApiError("Matn bo'sh yoki juda uzun (4000 belgigacha).")
        if target not in ("users", "chans", "both"):
            raise ApiError("Kimga yuborilishi noto'g'ri.")
        markup, bt, bu = None, str(body.get("btn_text", "")).strip(), str(body.get("btn_url", "")).strip()
        if bt and bu:
            if not re.match(r"https?://", bu):
                raise ApiError("Havola https:// bilan boshlanishi kerak.")
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=bt[:40], url=bu)]])
        if body.get("test"):
            try:
                await bot.send_message(user["id"], text, reply_markup=markup)
            except Exception as e:
                raise ApiError("Xabar formati xato: " + str(e)[:90])
            return {"test": True}
        if any(j["state"] == "run" for j in jobs.values()):
            raise ApiError("Boshqa yuborish davom etmoqda.")
        ids = []
        if target in ("users", "both"):
            ids += [r["id"] for r in db.execute("SELECT id FROM users WHERE banned=0")]
        if target in ("chans", "both"):
            ids += [c["id"] for c in connected_channels()]
        jid = str(int(time.time() * 1000))
        job = jobs[jid] = {"state": "run", "total": len(ids), "sent": 0, "failed": 0}

        async def run():
            for to in ids:
                for _ in range(2):
                    try:
                        await bot.send_message(to, text, reply_markup=markup)
                        job["sent"] += 1
                        break
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after + 1)
                    except Exception:
                        job["failed"] += 1
                        break
                await asyncio.sleep(0.05)
            job["state"] = "done"
        t = asyncio.create_task(run())
        running.add(t)
        t.add_done_callback(running.discard)
        return {"job": jid, **job}

    async def bc_status(user, body):
        j = jobs.get(str(body.get("job")))
        if not j:
            raise ApiError("Topilmadi.", 404)
        return dict(j)

    async def bc_info(user, body):
        return {"users": one("SELECT COUNT(*) FROM users WHERE banned=0"), "chans": len(connected_channels())}

    app.router.add_get("/admin", page)
    for path, fn in (("me", me), ("stats", stats), ("admins", admins), ("admins/add", admins_add),
                     ("admins/remove", admins_remove), ("emoji", emoji_list), ("emoji/save", emoji_save),
                     ("restart", restart), ("users", users_search), ("users/ban", users_ban),
                     ("users/points", users_points), ("broadcast", bc_start), ("broadcast/status", bc_status),
                     ("broadcast/info", bc_info)):
        app.router.add_post(f"/api/admin/{path}", api(fn))
