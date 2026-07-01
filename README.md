# 📱 Telefon tavsiya qiluvchi AI Telegram bot (MVP)

[![Klonlar soni](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/TeamLider9141/AI_phone_recommender_bot/main/.github/badges/clone-count.json)](https://github.com/TeamLider9141/AI_phone_recommender_bot)

<!-- CLONE_CHART:START -->
![Klonlar grafigi](https://quickchart.io/chart?c=%7B%22type%22%3A%22line%22%2C%22data%22%3A%7B%22labels%22%3A%5B%2206-30%22%5D%2C%22datasets%22%3A%5B%7B%22label%22%3A%22Umumiy%20klonlar%22%2C%22data%22%3A%5B88%5D%2C%22borderColor%22%3A%22%232563eb%22%2C%22backgroundColor%22%3A%22rgba%2837%2C99%2C235%2C0.15%29%22%2C%22fill%22%3Atrue%2C%22tension%22%3A0.3%2C%22pointRadius%22%3A0%7D%5D%7D%2C%22options%22%3A%7B%22plugins%22%3A%7B%22legend%22%3A%7B%22display%22%3Afalse%7D%2C%22title%22%3A%7B%22display%22%3Atrue%2C%22text%22%3A%22Repo%20klonlari%20%28kunlik%20yig%27indi%29%22%7D%7D%2C%22scales%22%3A%7B%22y%22%3A%7B%22beginAtZero%22%3Atrue%7D%7D%7D%7D&width=700&height=320&backgroundColor=white)
<!-- CLONE_CHART:END -->

Foydalanuvchi oddiy o'zbek tilida yozadi — bot Google Sheet'dagi bazadan eng mos
telefonlarni topib, izoh bilan tavsiya qiladi.

**Texnologiya:** Python · [aiogram](https://aiogram.dev) · Google Gemini 2.0 Flash
(tekin) · Google Sheets API (live).

## Qanday ishlaydi

```
Foydalanuvchi matni → Gemini (niyatni JSON filtrga aylantiradi)
                     → lokal filter + saralash (core/recommender.py)
                     → Gemini chiroyli o'zbekcha javob yozadi → Telegram
```

Butun baza Gemini'ga **yuborilmaydi** — faqat foydalanuvchi gapi va top natijalar.
Shu bois tekin kvota ichida qoladi. Gemini kaliti bo'lmasa, bot sodda regex rejimida
ham ishlayveradi.

## Fayllar

Loyiha vazifasiga ko'ra papkalarga bo'lingan:

| Papka | Vazifasi | Fayllar |
|-------|----------|---------|
| `core/` | Domen mantiqi — Telegram/tashqi manbalarga bog'liq emas | `config.py`, `models.py`, `ai.py`, `recommender.py` |
| `bot/` | Telegram (aiogram) qatlami | `main.py`, `keyboards.py`, `topic_guard.py` |
| `sources/` | Ma'lumot manbalari | `sheets.py`, `texnomart_scraper.py`, `texnomart_cache.py`, `bot_users.py` |
| `tests/` | Barcha testlar + smoke test | `test_*.py`, `smoke_test.py` |

| Fayl | Vazifasi |
|------|----------|
| `run.py` | Botni ishga tushirish entrypoint'i |
| `bot/main.py` | Telegram bot (buyruqlar, kunlik limit, matn handlerlari) |
| `core/ai.py` | Gemini: so'rovni filtrga aylantirish + javob yozish |
| `sources/sheets.py` | Google Sheet'dan baza o'qish + cache (CSV fallback) |
| `sources/texnomart_scraper.py` | Texnomart katalogidan live scraping |
| `core/recommender.py` | Qattiq filter + yumshoq saralash |
| `core/models.py` | `Phone`, `QueryFilter` strukturalari |
| `core/config.py` | `.env` sozlamalari |
| `sample_data.csv` | Kalitsiz sinash uchun namuna baza |

## Sozlash

### 1. Kutubxonalar
```bash
cd phone_rec
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Telegram token
[@BotFather](https://t.me/BotFather) → `/newbot` → tokenni oling.

### 3. Gemini API key (tekin)
[aistudio.google.com](https://aistudio.google.com) → **Get API key** → karta shart emas.

### 4. Google Sheets (live baza)
1. Google Sheet'ingizni **Viewer** yoki **Public** qilib ulashing.
2. Sheet ID'ni URL'dan oling: `docs.google.com/spreadsheets/d/`**`<SHEET_ID>`**`/edit`.
3. Agar service account ishlatmoqchi bo'lsangiz, [Google Cloud Console](https://console.cloud.google.com) →
   loyiha yarating → **Google Sheets API** ni yoqing → **Service Account** yarating →
   JSON key yuklab oling → `credentials.json` deb saqlang.
4. Service account foydalansangiz, Sheet'ingizni shu account email'iga
   (`...@...iam.gserviceaccount.com`) **Viewer** sifatida ulashing.

**Sheet ustunlari** (1-qator = sarlavha):
```
brand | model | ram | storage | color | camera_front | camera_back | processor | proc_tier | battery | os | price | detail_url | source_label
```
(`sample_data.csv` aynan shu tartibda — namuna sifatida ko'chiring.)

Agar Texnomart detail havolalarini ham ko'rsatmoqchi bo'lsangiz, ixtiyoriy
`detail_url` va `source_label` ustunlarini qo'shishingiz mumkin. `source_label`
uchun `texno` yoki `baza` qiymatlari ishlatiladi.

## Manba tanlash

Bot endi har bir so'rov uchun avval qaysi manbadan qidirishni so'raydi:

- `📚 Baza`
- `🛒 Texnomart`

Foydalanuvchi birini tanlagach, keyingi so'rovlar shu manbada ishlaydi.
Natija ostidagi `🔎 Boshqa bazadan izlash` tugmasi esa tanlovni qayta ochadi.

`TEXNOMART_BASE_URL`, `TEXNOMART_MAX_PAGES`, `TEXNOMART_MAX_ITEMS`,
`TEXNOMART_CACHE_PATH` va `TEXNOMART_CACHE_TTL` Texnomart cache/scraper
sozlamalari uchun qoladi. Bot Texnomart ro'yxatini JSON cache'ga saqlaydi;
keyingi qidiruvlar saytga chiqmasdan shu cache ustida ishlaydi. Cache eskirsa,
eski ro'yxat darhol qaytadi va yangilash orqa fonda boshlanadi. `detail_url`
saqlangani uchun natija manbalarida Texnomart linklari ko'rinadi.

Default qiymatlar cheklangan: 16 sahifa, 80 ta mahsulot, 30 daqiqa cache.
`PHONE_SOURCE` odatda `sheet` bo'lib qoladi va faqat texnik fallback/default
sifatida ishlaydi.

> Eslatma: agar `credentials.json` bo'lmasa, bot public share qilingan Sheet'ni
> authsiz o'qishga urinadi. Bu faqat Sheet haqiqatan ham viewer/public bo'lsa ishlaydi.

`proc_tier` — protsessor darajasi 1–100 (siz qo'yasiz). **Ixtiyoriy:** bo'sh
qoldirsangiz bot chipset nomidan taxminiy ball hisoblaydi.

### 5. `.env`
```bash
cp .env.example .env
# .env ni to'ldiring: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, GOOGLE_SHEET_ID, ADMIN_IDS
# Texnomart cache/scraper sozlamalari uchun:
# TEXNOMART_BASE_URL, TEXNOMART_MAX_PAGES, TEXNOMART_MAX_ITEMS,
# TEXNOMART_CACHE_PATH, TEXNOMART_CACHE_TTL
```

### 6. Ishga tushirish
```bash
python run.py
```

## Sinash (kalitlarsiz, offline)

`.env` bo'sh bo'lsa ham mantiqani sinash mumkin — `sample_data.csv` ishlatiladi.
Testlar repo ildizidan modul sifatida ishga tushiriladi (paketlararo import
uchun):

```bash
python3 -m tests.smoke_test
python3 -m tests.test_bot_commands
python3 -m tests.test_topic_guard
python3 -m tests.test_fallback_parse
python3 -m tests.test_texnomart_scraper
python3 -m tests.test_texnomart_cache
python3 -m tests.test_bot_users
```

## Buyruqlar
- `/start` — botni boshlash va asosiy tugmalarni ko'rsatish
- `/help` — qisqa qo'llanma
- `/clear` — foydalanuvchining oxirgi tavsiya xabarlarini va source tanlovini tozalash
- `/reload` — bazani majburiy yangilash (faqat `ADMIN_IDS`)
- `/settings` — limitlar va About users paneli (faqat `ADMIN_IDS`)
- Oddiy matn — telefon tavsiyasi

## User kuzatuvi

Har bir `/start` bosgan foydalanuvchi `BOT_USERS_PATH` dagi lokal JSON faylga
yoziladi. Birinchi marta start bosgan user haqida adminlarga xabar boradi.
`/settings` ichidagi `About users` tugmasi jami userlar va oxirgi start bosgan
foydalanuvchilar ro'yxatini ko'rsatadi. Bu runtime fayl GitHub'ga push qilinmaydi.

## Kunlik limit

Admin bo'lmagan har bir foydalanuvchi uchun standart limit `DAILY_LIMIT=5`.
Hisoblagich UTC+5 bo'yicha yangi kun boshlanganda yangilanadi. Adminlar limitdan
ozod va ularning menyusida `/settings` tugmasi ko'rinadi.

`/settings` orqali o'zgartirilgan limit bot ishlayotgan vaqt davomida amal qiladi.
Bot qayta ishga tushganda qiymat `.env` dagi `DAILY_LIMIT` dan qayta olinadi.

## Off-topic himoyasi

Bot tavsiya hisoblashdan oldin so'rov telefon mavzusiga aloqadorligini
tekshiradi. Birinchi aloqasiz so'rovda ogohlantirish beradi. Sozlangan
"bloklash vaqti" ichida yana aloqasiz so'rov(lar) yuborilsa (sozlangan
"urinishlar soni"ga yetganda), foydalanuvchi shu vaqtga jim bloklanadi.

Blok vaqtida matn, komandalar va inline tugmalar javobsiz qoldiriladi. Qoida
faqat oddiy foydalanuvchilarga tegishli — adminlar (`ADMIN_IDS`) off-topic
ogohlantirish/bloklashdan mustasno. Strike va bloklar xotirada saqlanadi, shu
sababli bot qayta ishga tushsa ular tozalanadi. Off-topic so'rovlar kunlik
telefon so'rovi limitidan foydalanmaydi.

Standart qiymatlar: bloklash vaqti **60 daqiqa**, urinishlar soni **2 ta**
(`.env`dagi `OFF_TOPIC_BLOCK_MINUTES` / `OFF_TOPIC_MAX_ATTEMPTS`). Admin
`/settings` panelidagi 2- va 3-qator tugmalari orqali botni qayta ishga
tushirmasdan real vaqtda o'zgartirishi mumkin.

## Narx: "gacha" vs "atrofida"
- **«5 mln gacha»** — qattiq chegara (`price_max`): 5 mln dan qimmati ko'rsatilmaydi.
- **«5 mln atrofida / chamasi / ~5 mln»** — yaqinlik (`price_target`): arzonroq VA
  qimmatroq, narxga **yaqinligi** bo'yicha saralangan (eng yaqini birinchi).
  Oraliq = target ±40% (5 mln uchun 3–7 mln). O'zgartirish: [recommender.py](core/recommender.py)
  `PRICE_BAND`.

## Filtr tugmalari (inline)
Har bir natija ostida saralash tugmalari chiqadi — bosilsa o'sha so'rov ustida
qayta saralanadi (tez, Gemini kvotasini sarflamaydi):

`🎯 Narxga yaqin` · `💰 Eng arzon` · `💎 Eng qimmat` · `📸 Kamera` ·
`🧠 Protsessor` · `⚡ RAM` · `💾 Xotira` · `🔋 Batareyka` · `🔟 Top 10 arzon`

So'rovning o'zida ham ishlaydi: «eng arzon 10 ta», «protsessor bo'yicha»,
«ko'p xotira» — Gemini/regex buni `sort_by` + `limit` ga aylantiradi.

Protsessor saralashi chipset nomidan taxminiy tier balini hisoblaydi
([recommender.py](core/recommender.py) `_PROC_SCORES`) — yangi chipsetlarni shu jadvalga qo'shing.

## Klonlar soni va grafigi

Sarlavha ostidagi raqamli belgi va o'sish grafigi vaqt o'tishi bilan **o'sib
boradi** — GitHub'ning o'zi `git clone`/"Download ZIP" statistikasini
(Insights → Traffic → Git clones) faqat oxirgi 14 kun uchun saqlaydi, shuning
uchun uni yo'qotmasdan yig'ib borish kerak:

- [`.github/workflows/clone-count.yml`](.github/workflows/clone-count.yml) har
  kuni (UTC 03:00) avtomatik ishga tushadi va
  [`.github/scripts/update_clone_stats.py`](.github/scripts/update_clone_stats.py)
  skriptini chaqiradi: GitHub Traffic API'dan yangi (hali hisoblanmagan) kunlar
  sonini o'qiydi, umumiy songa qo'shadi va oxirgi 60 kunlik tarixni
  [`.github/badges/clone-state.json`](.github/badges/clone-state.json) fayliga saqlaydi.
- Raqamli belgi: [`.github/badges/clone-count.json`](.github/badges/clone-count.json)
  ni shields.io "endpoint" formatida ko'rsatadi.
- O'sish grafigi: tarix asosida [QuickChart](https://quickchart.io) orqali
  chiziq grafigi generatsiya qilinadi va README'dagi
  `<!-- CLONE_CHART:START -->...<!-- CLONE_CHART:END -->` bloki ichiga
  avtomatik yoziladi — har kunlik yangilanishda rasm ham yangilanadi.

**Bir martalik sozlash (faqat repo egasi qila oladi):**
1. github.com/settings/tokens → **Generate new token (classic)** → `repo` scope
   bilan token yarating (Traffic API push-huquqi talab qiladi).
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**
   → nomi `TRAFFIC_PAT`, qiymati — yaratgan tokeningiz.
3. **Actions → Klon statistikasini yangilash → Run workflow** orqali birinchi
   marta qo'lda ishga tushiring (keyin avtomatik kunlik davom etadi).

## Keyingi bosqich (production)
Deploy (Railway/VPS), webhook, analitika, rasm/tugmali natijalar, ko'p tillilik (uz/ru),
rate-limit.
