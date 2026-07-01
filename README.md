# 📱 Telefon tavsiya qiluvchi AI Telegram bot (MVP)

Foydalanuvchi oddiy o'zbek tilida yozadi — bot Google Sheet'dagi bazadan eng mos
telefonlarni topib, izoh bilan tavsiya qiladi.

**Texnologiya:** Python · [aiogram](https://aiogram.dev) · Google Gemini 2.0 Flash
(tekin) · Google Sheets API (live).

## Qanday ishlaydi

```
Foydalanuvchi matni → Gemini (niyatni JSON filtrga aylantiradi)
                     → lokal filter + saralash (recommender.py)
                     → Gemini chiroyli o'zbekcha javob yozadi → Telegram
```

Butun baza Gemini'ga **yuborilmaydi** — faqat foydalanuvchi gapi va top natijalar.
Shu bois tekin kvota ichida qoladi. Gemini kaliti bo'lmasa, bot sodda regex rejimida
ham ishlayveradi.

## Fayllar

| Fayl | Vazifasi |
|------|----------|
| `main.py` | Telegram bot (buyruqlar, kunlik limit, matn handlerlari) |
| `ai.py` | Gemini: so'rovni filtrga aylantirish + javob yozish |
| `sheets.py` | Google Sheet'dan baza o'qish + cache (CSV fallback) |
| `texnomart_scraper.py` | Texnomart katalogidan live scraping |
| `recommender.py` | Qattiq filter + yumshoq saralash |
| `models.py` | `Phone`, `QueryFilter` strukturalari |
| `config.py` | `.env` sozlamalari |
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

`TEXNOMART_BASE_URL` va `TEXNOMART_MAX_PAGES` Texnomart scraper sozlamalari
uchun qoladi. `PHONE_SOURCE` odatda `sheet` bo'lib qoladi va faqat
texnik fallback/default sifatida ishlaydi.

> Eslatma: agar `credentials.json` bo'lmasa, bot public share qilingan Sheet'ni
> authsiz o'qishga urinadi. Bu faqat Sheet haqiqatan ham viewer/public bo'lsa ishlaydi.

`proc_tier` — protsessor darajasi 1–100 (siz qo'yasiz). **Ixtiyoriy:** bo'sh
qoldirsangiz bot chipset nomidan taxminiy ball hisoblaydi.

### 5. `.env`
```bash
cp .env.example .env
# .env ni to'ldiring: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, GOOGLE_SHEET_ID, ADMIN_IDS
# Texnomart scraper sozlamalari uchun: TEXNOMART_BASE_URL, TEXNOMART_MAX_PAGES
```

### 6. Ishga tushirish
```bash
python main.py
```

## Sinash (kalitlarsiz, offline)

`.env` bo'sh bo'lsa ham mantiqani sinash mumkin — `sample_data.csv` ishlatiladi:

```bash
python smoke_test.py
```

## Buyruqlar
- `/start` — botni boshlash va asosiy tugmalarni ko'rsatish
- `/help` — qisqa qo'llanma
- `/clear` — foydalanuvchining oxirgi tavsiya xabarlarini va source tanlovini tozalash
- `/reload` — bazani majburiy yangilash (faqat `ADMIN_IDS`)
- `/settings` — kunlik limitni tugmalar orqali o'zgartirish (faqat `ADMIN_IDS`)
- Oddiy matn — telefon tavsiyasi

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
  Oraliq = target ±40% (5 mln uchun 3–7 mln). O'zgartirish: [recommender.py](recommender.py)
  `PRICE_BAND`.

## Filtr tugmalari (inline)
Har bir natija ostida saralash tugmalari chiqadi — bosilsa o'sha so'rov ustida
qayta saralanadi (tez, Gemini kvotasini sarflamaydi):

`🎯 Narxga yaqin` · `💰 Eng arzon` · `💎 Eng qimmat` · `📸 Kamera` ·
`🧠 Protsessor` · `⚡ RAM` · `💾 Xotira` · `🔋 Batareyka` · `🔟 Top 10 arzon`

So'rovning o'zida ham ishlaydi: «eng arzon 10 ta», «protsessor bo'yicha»,
«ko'p xotira» — Gemini/regex buni `sort_by` + `limit` ga aylantiradi.

Protsessor saralashi chipset nomidan taxminiy tier balini hisoblaydi
([recommender.py](recommender.py) `_PROC_SCORES`) — yangi chipsetlarni shu jadvalga qo'shing.

## Keyingi bosqich (production)
Deploy (Railway/VPS), webhook, analitika, rasm/tugmali natijalar, ko'p tillilik (uz/ru),
rate-limit.
