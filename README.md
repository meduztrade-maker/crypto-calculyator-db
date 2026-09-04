# MEDUZ TRADING JOURNAL — Telegram Bot

Professional crypto futures trading journal bot. Trade yaratish, pending → active → closed oqimi,
kunlik/haftalik/custom statistikalar (matn + premium rasm), leverage calculator, real-time narx
alertlari va PostgreSQL backup/restore (Telegram private kanal orqali).

## 🧱 Stack

- Python 3.12
- [aiogram 3.x](https://docs.aiogram.dev/) — Telegram bot framework (FSM asosida)
- SQLAlchemy 2.x (async) + asyncpg — PostgreSQL uchun
- Alembic — DB migratsiyalari
- Pillow — premium report rasm generatori (font bundle qilingan, `assets/fonts/`)
- APScheduler — kunlik avtomatik backup + har 30 soniyada alert tekshiruvi
- aiohttp — Binance public API'dan real-time narx olish uchun
- Railway — deploy (Railpack builder)

## 📁 Fayl tuzilishi

```
meduz-trading-journal-bot/
├── bot/
│   ├── main.py                 # Entry point: dispatcher, routerlar, scheduler
│   ├── config.py               # Env-based sozlamalar
│   ├── database/
│   │   ├── models.py           # User, Trade, Backup, Alert (SQLAlchemy ORM)
│   │   ├── engine.py           # Async engine/session
│   │   └── crud.py             # DB amallari (race-safe, with_for_update)
│   ├── handlers/
│   │   ├── start.py            # /start, bosh menyu
│   │   ├── trade_create.py     # ➕ Trade qo'shish FSM
│   │   ├── pending.py          # ⏳ Pending: Activate/Missed/Delete
│   │   ├── active.py           # 🟢 Active: SL/B-U/TP yopish
│   │   ├── reports.py          # 📊 Kunlik/Haftalik/Custom hisobot
│   │   ├── leverage.py         # 🧮 Leverage calculator
│   │   ├── recent_trades.py    # 🗑 Oxirgi 5 ta trade — istalganini o'chirish
│   │   ├── alerts.py           # 🔔 Narx alertlari (coin + narx → bildirishnoma)
│   │   └── settings.py         # ⚙️ Margin, backup, restore
│   ├── services/
│   │   ├── stats.py            # SQL-aggregation statistikalar
│   │   ├── report_image.py     # Premium PNG report
│   │   ├── leverage_calc.py    # Leverage formulasi
│   │   ├── backup.py           # JSON dump/restore (pure Python) + Telegram kanal + retention
│   │   ├── price_feed.py       # Binance public API orqali real-time narx
│   │   └── alert_checker.py    # Background job: alertlarni narx bilan solishtiradi
│   ├── states/trade_states.py  # Barcha FSM state guruhlari
│   ├── keyboards/inline.py     # Inline tugmalar + typed CallbackData
│   ├── middlewares/db.py       # Har update uchun DB session + user context
│   └── utils/formatting.py     # Parsing, decimal formatting, xatolik handling
├── alembic/                    # Migratsiyalar (async env.py)
├── assets/fonts/                # Report rasm uchun bundle qilingan DejaVu fontlar
├── requirements.txt
├── Procfile                     # worker: alembic upgrade head && python -m bot.main
└── .env.example
```

## ⚙️ O'rnatish (lokal)

```bash
git clone <repo-url>
cd meduz-trading-journal-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # qiymatlarni to'ldiring
```

`.env` da kerakli o'zgaruvchilar (`.env.example` da izohi bilan):

| Nomi | Izoh |
|---|---|
| `BOT_TOKEN` | @BotFather'dan olingan token |
| `DATABASE_URL` | PostgreSQL ulanish satri |
| `ADMIN_ID` | Bot egasining Telegram user ID'si |
| `BACKUP_CHANNEL_ID` | Backup uchun private kanal ID (`-100...`) |
| `TIMEZONE` | Default: `Asia/Tashkent` |
| `DEFAULT_MARGIN` | Yangi userlar uchun boshlang'ich margin (default 500) |

Migratsiyalarni ishga tushirish:

```bash
alembic upgrade head
```

Botni ishga tushirish:

```bash
python -m bot.main
```

## ☁️ Railway'ga deploy

1. Railway'da yangi loyiha oching, GitHub repo'ni ulang (bitta service — ikkita emas, aks holda
   ikkala instance bir xil `BOT_TOKEN` bilan pollling qilib "Conflict" xatosi beradi).
2. **PostgreSQL** uchun alohida service qo'shing (`DATABASE_URL` shu servisdan referens sifatida
   beriladi — `${{Postgres.DATABASE_URL}}`).
3. Bot service Variables bo'limida `BOT_TOKEN`, `ADMIN_ID`, `BACKUP_CHANNEL_ID`, `TIMEZONE`,
   `DATABASE_URL` qo'shing.
4. Start command `Procfile`'dan avtomatik olinadi: `alembic upgrade head && python -m bot.main` —
   shu bilan har deployda migratsiya ham avtomatik ishlaydi.

**Diqqat — Railpack va preDeployCommand:** Railway'ning yangi "Railpack" builder'i (`nixpacks.toml`
o'rniga) ishlatiladi va tajribada shu loyihada servis darajasidagi `preDeployCommand` sozlamasi
amalda ishlamadi — shu sabab migratsiya to'g'ridan-to'g'ri `Procfile`'dagi `worker` buyrug'i ichiga
(`&&` bilan) qo'shilgan. Agar kelajakda alohida release-fazasi kerak bo'lsa, avval buni real deployda
tekshirib ko'ring.

**Server almashtirilganda** (spec §23): yangi Railway loyihasida shu repo'ni qayta deploy qiling,
xuddi shu environment variables'ni kiriting, PostgreSQL'ni yangidan ulang (yoki backup'dan restore
qiling — pastga qarang). Trade tarixi PostgreSQL'da saqlanadi, kod stateless.

## 🔄 Migratsiyalar

Yangi model o'zgarishi qilinganda:

```bash
alembic revision --autogenerate -m "tavsif"
alembic upgrade head
```

Barcha migratsiyalar (`alembic/versions/`) ushbu loyihani tuzish jarayonida **haqiqiy local
PostgreSQL 16 instance'ga qarshi** generatsiya qilingan va qo'llanilgan (pastga qarang).

## ☁️ Backup / Restore

Backup **pure-Python JSON dump** sifatida ishlaydi (`users` + `trades` jadvallari) — `pg_dump`/
`pg_restore` binary'lariga bog'liq emas, shuning uchun Railway qanday builder ishlatishidan qat'i
nazar ishlайdi (birinchi versiyada `pg_dump` orqali qilingan edi, lekin Railway'ning Railpack
builder'i uni image'ga o'rnatmagani sabab `FileNotFoundError: pg_dump` bilan ishlamay qolgan edi —
shu sabab pure-Python yondashuvga o'tkazildi).

- Har kuni soat **03:00 (Asia/Tashkent)** avtomatik backup: JSON → gzip → private Telegram kanalga
  hujjat sifatida yuboriladi, xabarning `file_id`'si DB'da saqlanadi (restore uchun).
- Retention: kunlik → 30 kun, haftalik (har Dushanba) → 12 hafta, oylik (har oyning 1-kuni) → 12 oy.
  **Eng oxirgi muvaffaqiyatli backup hech qachon o'chirilmaydi.**
- `⚙️ Sozlamalar → ☁️ Backup Now` — qo'lda backup (faqat admin).
- `⚙️ Sozlamalar → 🔄 Restore` — oxirgi muvaffaqiyatli backup'ni tasdiqlash bilan tiklaydi (faqat
  admin, `⚠️` ogohlantirish + tasdiqlash tugmasi bilan). Restore `users`+`trades` jadvallarini
  to'liq almashtiradi va PK sequence'larni qayta tekislaydi.

## 🧭 Navigatsiya dizayni

Bot ikkita darajali navigatsiyadan foydalanadi — professional Telegram botlarda keng qo'llaniladigan
pattern:

- **Pastki doimiy menyu** (`ReplyKeyboardMarkup`, `/start`da bir marta o'rnatiladi) — 8 ta asosiy
  bo'lim doim matn kiritish maydonining ustida turadi, chatni qanchalik pastga tushirmang, hech qachon
  yo'qolmaydi. Har qanday bo'lim tugmasini bosish **darhol ishlaydi** — hatto boshqa bir amal
  o'rtasida (masalan entry narxi kiritilayotganda) bosilsa ham: `menu.py` routeri eng birinchi
  ro'yxatdan o'tkazilgan (`main.py`da `start` dan keyin, qolgan hamma state-bog'liq routerlardan
  oldin), shuning uchun u har doim ustunlik qiladi, joriy FSM holatini tozalab, so'ralgan bo'limga
  o'tkazadi — "adashib qolish" imkonsiz.
- **Ro'yxat → tafsilot → orqaga** pattern — Pending, Active, Oxirgi tradelar, Alert bo'limlari endi
  har bir element uchun alohida xabar yubormaydi (avval shunday edi va chatni "bardak" qilib
  yuborardi). Buning o'rniga: bitta xabar ro'yxatni tugmalar sifatida ko'rsatadi → tanlangan element
  o'sha **bitta xabar ichida** (`edit_text`) tafsilotga almashadi, harakat tugmalari + **🔙 Orqaga**
  bilan → orqaga bosilsa yana o'sha xabar ro'yxatga qaytadi. Xabarlar soni ko'paymaydi, eski
  tugmalar "osilib" qolmaydi.
- Screenshot talab qiladigan oqimlar (trade qo'shish, SL/B-U/TP yopish) tabiatan bir nechta xabar
  talab qiladi (bot navbat bilan so'raydi, user matn/rasm yuboradi) — bu qismlarda ham har bosqichda
  **❌ Bekor qilish** tugmasi bor va yakunda natija bitta aniq xabar bilan ko'rsatiladi.

## 🗑 Oxirgi tradelar

Bosh menyudagi **🗑 Oxirgi tradelar** — statusidan qat'i nazar (pending/active/closed/missed) oxirgi
5 ta trade'ni ko'rsatadi, har birida **🗑 O'chirish** tugmasi bor (tasdiqlash bilan). Bu, masalan,
xato kiritilgan trade'ni journal tarixidan butunlay olib tashlash uchun.

## 🔔 Narx alertlari

Bosh menyudagi **🔔 Alert** — coin nomi va maqsadli narxni kiritish orqali alert qo'yiladi
(masalan: `BTCUSDT` → `112000`). Narx Binance'ning ochiq API'sidan olinadi:

- Alert qo'yilganda joriy narx bilan solishtirilib, avtomatik yo'nalish aniqlanadi (narx oshib shu
  darajaga yetsa ⬆️, tushib yetsa ⬇️ — qo'shimcha savol berilmaydi).
- Background job har **30 soniyada** barcha faol alertlarni bitta so'rov bilan (Binance'ning to'liq
  ticker ro'yxati) tekshiradi — N ta alert bo'lsa ham 1 ta HTTP so'rov.
- Narx yetganda foydalanuvchiga darhol Telegram xabari yuboriladi, alert bir martalik (TRIGGERED
  holatiga o'tadi, qayta ishlamaydi).
- **🔔 Alert → ❌ Bekor qilish** — istalgan faol alertni o'chirish mumkin.

## 🖼 Hisobot rasmi (premium dashboard dizayni)

`📊 Hisobot` bo'limida yaratiladigan PNG endi oddiy statistika kartasi emas — professional prop-firm/
birja uslubidagi to'liq dashboard (Pillow bilan qo'lda chizilgan, tashqi chart kutubxonasiz):

- **Equity curve** — davr ichidagi barcha yopilgan tradelarning kumulyativ R qiymati chiziq
  grafik + gradient fon bilan (foyda bo'lsa yashil, zarar bo'lsa qizil), grid chiziqlar va R
  qiymatlari bilan
- 4 ta stat-chip: Win Rate, Average RR, **Profit Factor** (yangi — yutuqlar yig'indisi / zararlar
  yig'indisi, faqat zarar bo'lmasa "∞"), Trades
- Win/B-U/Loss taqsimoti — rangli progress-bar + legend
- Coinlar ro'yxati — har birida rangli status-nuqta va o'ng tomonda natija badge'i
- Barcha holatlar uchun tekshirildi: foydali davr, zararli davr (qizil equity curve), va bo'sh davr
  (0 trade) — hech biri xato bermaydi

Matnli hisobotga ham **Profit Factor** qatori qo'shildi.

## 🧪 Test natijalari

Loyiha qurilishi davomida haqiqiy local PostgreSQL 16 instance ishga tushirilib, quyidagilar
tekshirildi:

- ✅ `alembic revision --autogenerate` + `alembic upgrade head` — barcha migratsiyalar (jumladan
  `alerts` jadvali) xatosiz yaratildi va qo'llandi
- ✅ Trade lifecycle: yaratish → pending → activate → close (SL va TP/RR bilan)
- ✅ Statistika hisob-kitobi (win rate, total R, average RR, coin breakdown) to'g'ri natija berdi
- ✅ Premium report rasm generatsiyasi (Pillow) — muvaffaqiyatli PNG chiqdi
- ✅ Leverage calculator — spec misolidagi natija bilan mos keldi (Margin $500, Risk $50, SL 2% → **5X**)
- ✅ Duplicate-click himoyasi: allaqachon yopilgan trade'ni qayta yopishga urinish to'g'ri rad etildi
- ✅ **Backup JSON dump/restore round-trip** — real DB'ga real ma'lumot yozilib, dump olinib, DB
  o'zgartirilib, restore qilinib, asl holatga aniq qaytgani tasdiqlandi
- ✅ Alert CRUD: yaratish (yo'nalish avtomatik aniqlanishi), faol ro'yxat, trigger qilish, bekor
  qilish — barchasi real DB'da tekshirildi
- ✅ Recent-trades force-delete (istalgan statusdagi trade'ni o'chirish) tekshirildi
- ✅ **Real production'da (Railway) deploy qilindi va sinovdan o'tkazildi** — shu jarayonda 3 ta real
  xatolik topilib tuzatildi: (1) `greenlet` paketi requirements.txt'da yo'q edi, (2) Railway'ning
  Railpack builder'i migratsiyani ishga tushirmagani, (3) `pg_dump` binary Railpack image'ida yo'qligi
  — barchasi yuqorida tavsiflangan
- ⚠️ Binance API'ga so'rov (`price_feed.py`) qurilish sandbox'ida tarmoq cheklovi sabab test
  qilinmadi — Railway'da to'liq internet mavjud, shuning uchun productionda ishlaydi, lekin birinchi
  alert qo'yilganda natijani tekshirib ko'rish tavsiya etiladi
- ✅ Navigatsiya qayta qurilgandan keyin `Dispatcher` to'liq yig'ilishi va router tartibi
  (`menu` routeri `start`dan keyin, qolgan hamma state-bog'liq routerlardan oldin turishi) dastur
  ichida tekshirildi
- ✅ Premium report rasm (equity curve, profit factor, win/loss bar) — real DB ma'lumoti bilan
  (`compute_period_stats` → `render_report_image`) uchtadan holatda tekshirildi: foydali davr,
  butunlay zararli davr, va 0 tradeli bo'sh davr — barchasi to'g'ri chiqdi

## ⚠️ Ma'lum cheklovlar

- Bot **long polling** rejimida ishlaydi (webhook emas) — **faqat bitta** Railway service shu
  `BOT_TOKEN` bilan ishlashi kerak; ikkinchi instance qo'shilsa Telegram "Conflict" xatosi beradi.
- Restore doim **eng oxirgi** muvaffaqiyatli backup'ni tiklaydi (ixtiyoriy sanadan tanlash yo'q).
- Alert narxlari faqat Binance'da mavjud spot juftliklar uchun ishlaydi (masalan `BTCUSDT`); futures-
  only yoki Binance'da yo'q coinlar uchun xato beradi.
- Group signal, real-time chart kabi funksiyalar ushbu texnik topshiriqda so'ralmagan, shuning uchun
  kiritilmagan.

## 🚀 Kelgusi yaxshilanishlar

- Webhook rejimiga o'tish + Redis FSM storage (ko'p worker uchun)
- Restore'da backup ro'yxatidan sana tanlash imkoniyati
- Alert uchun takrorlanuvchi (bir martalik emas) rejim
- Coin bo'yicha filtrlab statistika ko'rish
- Admin panel (barcha userlar statistikasi, umumiy backup monitoring)
