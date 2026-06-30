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
| `main.py` | Telegram bot (start, matn handler, /reload) |
| `ai.py` | Gemini: so'rovni filtrga aylantirish + javob yozish |
| `sheets.py` | Google Sheet'dan baza o'qish + cache (CSV fallback) |
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
1. [Google Cloud Console](https://console.cloud.google.com) → loyiha yarating.
2. **Google Sheets API** ni yoqing.
3. **Service Account** yarating → JSON key yuklab oling → `credentials.json` deb saqlang.
4. Google Sheet'ingizni service account email'iga (`...@...iam.gserviceaccount.com`)
   **Viewer** sifatida ulashing.
5. Sheet ID'ni URL'dan oling: `docs.google.com/spreadsheets/d/`**`<SHEET_ID>`**`/edit`.

**Sheet ustunlari** (1-qator = sarlavha):
```
brand | model | ram | storage | color | camera_front | camera_back | processor | proc_tier | battery | os | price
```
(`sample_data.csv` aynan shu tartibda — namuna sifatida ko'chiring.)

`proc_tier` — protsessor darajasi 1–100 (siz qo'yasiz). **Ixtiyoriy:** bo'sh
qoldirsangiz bot chipset nomidan taxminiy ball hisoblaydi.

### 5. `.env`
```bash
cp .env.example .env
# .env ni to'ldiring: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, GOOGLE_SHEET_ID, ADMIN_IDS
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
- `/start` — qo'llanma
- `/reload` — bazani majburiy yangilash (faqat `ADMIN_IDS`)
- Oddiy matn — telefon tavsiyasi

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
