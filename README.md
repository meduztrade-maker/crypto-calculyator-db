# MEDUZ TRADING JOURNAL — Telegram Bot

Professional crypto futures trading journal bot. Trade yaratish, pending → active → closed oqimi,
kunlik/haftalik/custom statistikalar (matn + premium rasm), leverage calculator va PostgreSQL
backup/restore (Telegram private kanal orqali) — to'liq texnik topshiriqqa asosan qurilgan.

## 🧱 Stack

- Python 3.12
- [aiogram 3.x](https://docs.aiogram.dev/) — Telegram bot framework (FSM asosida)
- SQLAlchemy 2.x (async) + asyncpg — PostgreSQL uchun
- Alembic — DB migratsiyalari
- Pillow — premium report rasm generatori (font bundle qilingan, `assets/fonts/`)
- APScheduler — kunlik avtomatik backup
- Railway — deploy (nixpacks)

## 📁 Fayl tuzilishi

```
meduz-trading-journal-bot/
├── bot/
│   ├── main.py                # Entry point: dispatcher, routerlar, scheduler
│   ├── config.py              # Env-based sozlamalar
│   ├── database/
│   │   ├── models.py          # User, Trade, Backup (SQLAlchemy ORM)
│   │   ├── engine.py          # Async engine/session
│   │   └── crud.py            # DB amallari (race-safe, with_for_update)
│   ├── handlers/
│   │   ├── start.py           # /start, bosh menyu
│   │   ├── trade_create.py    # ➕ Trade qo'shish FSM
│   │   ├── pending.py         # ⏳ Pending: Activate/Missed/Delete
│   │   ├── active.py          # 🟢 Active: SL/B-U/TP yopish
│   │   ├── reports.py         # 📊 Kunlik/Haftalik/Custom hisobot
│   │   ├── leverage.py        # 🧮 Leverage calculator
│   │   └── settings.py        # ⚙️ Margin, backup, restore
│   ├── services/
│   │   ├── stats.py           # SQL-aggregation statistikalar
│   │   ├── report_image.py    # Premium PNG report
│   │   ├── leverage_calc.py   # Leverage formulasi
│   │   └── backup.py          # pg_dump/pg_restore + Telegram kanal + retention
│   ├── states/trade_states.py # Barcha FSM state guruhlari
│   ├── keyboards/inline.py    # Inline tugmalar + typed CallbackData
│   ├── middlewares/db.py      # Har update uchun DB session + user context
│   └── utils/formatting.py    # Parsing, decimal formatting, xatolik handling
├── alembic/                   # Migratsiyalar (async env.py)
├── assets/fonts/               # Report rasm uchun bundle qilingan DejaVu fontlar
├── requirements.txt
├── nixpacks.toml               # Railway build config (postgresql-client o'rnatadi)
├── Procfile
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

1. Railway'da yangi loyiha oching, GitHub repo'ni ulang.
2. **PostgreSQL plugin** qo'shing — Railway avtomatik `DATABASE_URL` beradi (`postgres://...` formatida;
   `bot/config.py` buni avtomatik `postgresql+asyncpg://` ga o'giradi).
3. Variables bo'limida `BOT_TOKEN`, `ADMIN_ID`, `BACKUP_CHANNEL_ID`, `TIMEZONE` qo'shing.
4. `nixpacks.toml` PostgreSQL client (`pg_dump`/`pg_restore`) ni build bosqichida o'rnatadi — qo'shimcha
   sozlash shart emas.
5. Deploy avtomatik: `alembic upgrade head` ishga tushadi, keyin bot polling rejimida ishlaydi.

**Server almashtirilganda** (spec §23): yangi Railway loyihasida shu repo'ni qayta deploy qiling,
xuddi shu environment variables'ni kiriting, PostgreSQL plugin'ni yangidan ulang (yoki backup'dan
restore qiling — pastga qarang). Trade tarixi PostgreSQL'da saqlanadi, kod stateless.

## 🔄 Migratsiyalar

Yangi model o'zgarishi qilinganda:

```bash
alembic revision --autogenerate -m "tavsif"
alembic upgrade head
```

Boshlang'ich migratsiya (`alembic/versions/`) ushbu loyihani tuzish jarayonida **haqiqiy local
PostgreSQL 16 instance'ga qarshi** generatsiya qilingan va `alembic upgrade head` orqali sinovdan
o'tkazilgan (pastga qarang).

## ☁️ Backup / Restore

- Har kuni soat **03:00 (Asia/Tashkent)** avtomatik backup: `pg_dump -Fc` → gzip → private Telegram
  kanalga hujjat sifatida yuboriladi, xabar `file_id` DB'da saqlanadi (restore uchun).
- Retention: kunlik → 30 kun, haftalik (har Dushanba) → 12 hafta, oylik (har oyning 1-kuni) → 12 oy.
  **Eng oxirgi muvaffaqiyatli backup hech qachon o'chirilmaydi.**
- `⚙️ Sozlamalar → ☁️ Backup Now` — qo'lda backup (faqat admin).
- `⚙️ Sozlamalar → 🔄 Restore` — oxirgi muvaffaqiyatli backup'ni tasdiqlash bilan tiklaydi (faqat admin,
  `⚠️` ogohlantirish + tasdiqlash tugmasi bilan).

**Muhim:** `pg_dump`/`pg_restore` deploy muhitida mavjud bo'lishi kerak — Railway uchun bu
`nixpacks.toml` orqali avtomatik ta'minlangan.

## 🧪 Test natijalari

Loyiha qurilishi davomida haqiqiy local PostgreSQL 16 instance ishga tushirilib, quyidagilar
tekshirildi:

- ✅ `alembic revision --autogenerate` + `alembic upgrade head` — schema xatosiz yaratildi va qo'llandi
- ✅ Trade lifecycle: yaratish → pending → activate → close (SL va TP/RR bilan)
- ✅ Statistika hisob-kitobi (win rate, total R, average RR, coin breakdown) to'g'ri natija berdi
- ✅ Premium report rasm generatsiyasi (Pillow) — muvaffaqiyatli PNG chiqdi
- ✅ Leverage calculator — spec misolidagi natija bilan mos keldi (Margin $500, Risk $50, SL 2% → **5X**)
- ✅ Duplicate-click himoyasi: allaqachon yopilgan trade'ni qayta yopishga urinish to'g'ri rad etildi
  (`with_for_update` + status tekshiruvi)
- ⚠️ Telegram Bot API bilan bog'liq qismlar (screenshot yuborish, backup kanaliga hujjat yuborish,
  restore'da fayl yuklab olish) haqiqiy `BOT_TOKEN` va kanal bo'lmagani sabab **live Telegram muhitida
  test qilinmadi** — kod aiogram 3.x rasmiy API'siga mos yozilgan, lekin birinchi real ishga
  tushirishda sinab ko'rish tavsiya etiladi

## ⚠️ Ma'lum cheklovlar

- Bot **long polling** rejimida ishlaydi (webhook emas) — bitta instance uchun yetarli, ko'p instance
  kerak bo'lsa webhook + Redis-based FSM storage'ga o'tish kerak bo'ladi (hozir in-memory FSM storage).
- `pg_dump`/`pg_restore` subprocess orqali chaqiriladi — Railway'dan boshqa platformaga deploy
  qilinsa, o'sha muhitda ham postgresql-client mavjudligini tekshiring.
- Restore doim **eng oxirgi** muvaffaqiyatli backup'ni tiklaydi (ixtiyoriy sanadan tanlash yo'q) —
  soddalik uchun shunday qilindi.
- Group signal, real-time narx/chart, price alert kabi funksiyalar ushbu texnik topshiriqda
  so'ralmagan, shuning uchun kiritilmagan.

## 🚀 Kelgusi yaxshilanishlar

- Webhook rejimiga o'tish + Redis FSM storage (ko'p worker uchun)
- Restore'da backup ro'yxatidan sana tanlash imkoniyati
- Coin bo'yicha filtrlab statistika ko'rish
- Inline "🖼 Rasm" tugmasi — hozir rasm avtomatik matn bilan birga yuboriladi, xohlasa alohida
  so'rash imkoniyati qo'shish mumkin
- Admin panel (barcha userlar statistikasi, umumiy backup monitoring)
