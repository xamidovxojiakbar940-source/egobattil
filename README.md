# Batl bot — Render'ga deploy

## Fayllar
bot.py, games.py, webapp.py, verify.html, emojis.py, requirements.txt, render.yaml, .python-version

## Deploy (Render)
1. Papkani GitHub'ga push qiling (yangi repo).
2. Render → New → Blueprint → repo'ni tanlang (render.yaml avtomatik o'qiladi).
   Qo'lda qilsangiz: New → Web Service, Build: `pip install -r requirements.txt`, Start: `python bot.py`.
3. Environment o'zgaruvchilari:
   - BOT_TOKEN   — @BotFather tokeni
   - ADMIN_IDS   — admin ID'lari, vergul bilan (123,456)
   - WEBAPP_URL  — https://<servis-nomi>.onrender.com  (qurilma tekshiruvi uchun)
   - DB_PATH     — /data/bot.db  (Persistent Disk, mount: /data)
   - EMOJI_IDS   — ixtiyoriy, premium emoji ID'lari JSON: {"battle":"123..."}
4. Faqat BITTA instance ishlating (polling).

## Muhim
- Persistent Disk faqat pullik rejada (Starter). Bepul rejada bot.db har restartda o'chadi
  va servis 15 daqiqadan keyin uxlaydi.
- Disk ulamasangiz ma'lumotlar yo'qoladi.

## Kanalda #batl
Botni kanalga admin qiling → kanalga `#batl` yozing → bot shu kanalning o'ziga battle postini darhol chiqaradi
(nomi "OVOZ BATL BOSHLANDI", sovrin "Hozircha Sir", tugash vaqti yo'q).
Battle egasi kanal egasi (yoki post imzosiga mos admin). To'xtatish: botda "Mening battlelarim" → Battle to'xtatish.
Kanal ochiq (username'li) bo'lishi kerak. Nom/sovrin/vaqt kiritib yaratish uchun botdagi "Battle yaratish" tugmasi bor.

## Admin panel (/admin)
- 🔒 Majburiy kanallar — botdan foydalanish uchun obuna shart bo'lgan kanallar (bot kanalda admin, kanal ochiq bo'lishi kerak).
  Adminlar bundan ozod. Obunasiz foydalanuvchiga kanal tugmalari va «Tekshirish» chiqadi; deep-link (ovoz/qatnashish) obunadan keyin davom etadi.
- 📢 Xabar yuborish — kimga: foydalanuvchilarga / ulangan kanallarga / ikkalasiga. Yuborishdan oldin tasdiqlash so'raladi.
- 📋 Ulangan kanallar — battle/konkurs yaratilgan kanallar ro'yxati.

## Web App admin panel (/admin → «🖥 Web panelni ochish»)
Faqat adminlar uchun (Telegram imzosi + admin ro'yxati tekshiriladi). WEBAPP_URL sozlangan bo'lishi shart.
- 📊 Statistika: foydalanuvchilar, battle/konkurs, kanallar, 7 kunlik o'sish grafigi.
- 🛡 Adminlar: ID bo'yicha qo'shish/o'chirish (bazada saqlanadi; ADMIN_IDS dagilar asosiy admin, o'chirib bo'lmaydi).
- ✨ Premium emoji: 38 ta joy uchun ID kiritish (Telegram orqali tekshiriladi). «Tartib bilan joylash»: botga premium emojilarni
  ro'yxat tartibida yuborasiz → bot ID ro'yxatini qaytaradi → panelga tashlaysiz. Saqlagach «Qo'llash» botni qayta ishga tushiradi.
