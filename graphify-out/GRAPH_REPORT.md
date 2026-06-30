# Graph Report - phone_rec  (2026-06-30)

## Corpus Check
- 9 files · ~3,986 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 102 nodes · 121 edges · 10 communities (9 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `79e87c7c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]

## God Nodes (most connected - your core abstractions)
1. `📱 Telefon tavsiya qiluvchi AI Telegram bot (MVP)` - 9 edges
2. `Sozlash` - 7 edges
3. `_row_to_phone()` - 6 edges
4. `load_phones()` - 6 edges
5. `recommend()` - 6 edges
6. `Phone` - 5 edges
7. `format_reply()` - 5 edges
8. `QueryFilter` - 4 edges
9. `_sort_phones()` - 4 edges
10. `parse_query()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `_row_to_phone()` --calls--> `Phone`  [INFERRED]
  sheets.py → models.py
- `recommend()` --calls--> `QueryFilter`  [INFERRED]
  recommender.py → models.py
- `_fallback_parse()` --calls--> `QueryFilter`  [INFERRED]
  ai.py → models.py
- `main()` --calls--> `recommend()`  [INFERRED]
  smoke_test.py → recommender.py

## Communities (10 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.14
Nodes (16): _matches_hard(), _proc_value(), _processor_score(), Filtrlash + saralash mantiqi (LLM'siz, sof Python). Gemini faqat niyatni o'qiydi, Yumshoq saralash bali — kattaroq = yaxshiroq mos., Mos telefonlarni qaytaradi.      Return: (telefonlar, relaxed) — relaxed=True bo, Qattiq shartlar: biror shart buzilsa telefon tushib qoladi., Chipset nomidan taxminiy quvvat bali (heuristik). Topilmasa 0. (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.23
Nodes (13): get_phones(), _load_from_csv(), _load_from_sheet(), load_phones(), _norm_key(), Google Sheet (live) dan telefonlar bazasini o'qish + RAM cache (TTL).  Agar Goog, Cache'langan ro'yxat; TTL o'tgan bo'lsa qayta yuklaydi., Majburiy qayta yuklash (admin /reload). Yuklangan telefonlar sonini qaytaradi. (+5 more)

### Community 2 - "Community 2"
Cohesion: 0.22
Nodes (13): _empty_reply(), _fallback_parse(), format_reply(), _get_model(), _parse_price(), parse_query(), _phone_dict(), Gemini (tekin) bilan ishlash: foydalanuvchi matnini filtrga aylantirish va javob (+5 more)

### Community 3 - "Community 3"
Cohesion: 0.19
Nodes (10): build_dispatcher(), main(), on_sort(), on_text(), _process(), Telegram bot entrypoint (aiogram 3.x). Telefon tavsiya qiluvchi AI bot., So'rovni qayta ishlaydi. Return: (javob matni, ishlatilgan filtr)., Tugma bosilganda: saqlangan filtrni qayta saralash (tez, Gemini'siz). (+2 more)

### Community 4 - "Community 4"
Cohesion: 0.18
Nodes (10): Buyruqlar, code:block1 (Foydalanuvchi matni → Gemini (niyatni JSON filtrga aylantira), code:bash (python smoke_test.py), Fayllar, Filtr tugmalari (inline), Keyingi bosqich (production), Narx: "gacha" vs "atrofida", Qanday ishlaydi (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.18
Nodes (11): 1. Kutubxonalar, 2. Telegram token, 3. Gemini API key (tekin), 4. Google Sheets (live baza), 5. `.env`, 6. Ishga tushirish, code:bash (cd phone_rec), code:block3 (brand | model | ram | storage | color | camera_front | camer) (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.2
Nodes (6): Phone, QueryFilter, Ma'lumot strukturalari: Phone (bazadagi bitta telefon) va QueryFilter (so'rov fi, Bazadagi (Google Sheet) bitta telefon yozuvi., Telegram javobi uchun qisqa, o'qiladigan spetsifikatsiya satri., Gemini foydalanuvchi matnidan ajratib oladigan strukturali filtr.

### Community 7 - "Community 7"
Cohesion: 0.47
Nodes (4): Config, _int_list(), load_config(), Konfiguratsiya: .env fayldan token/kalit/sozlamalarni o'qiydi.

### Community 8 - "Community 8"
Cohesion: 0.5
Nodes (3): Inline tugmalar: natijalarni qayta saralash filtrlari., So'rov natijasi ostidagi saralash tugmalari. active = belgilangan kalit., results_keyboard()

## Knowledge Gaps
- **42 isolated node(s):** `Google Sheet (live) dan telefonlar bazasini o'qish + RAM cache (TTL).  Agar Goog`, `8 GB', '5,000,000', '5000mAh' -> int; bo'sh/xato -> None.`, `Manbadan telefonlar ro'yxatini yuklaydi (cachesiz, to'g'ridan-to'g'ri).`, `Cache'langan ro'yxat; TTL o'tgan bo'lsa qayta yuklaydi.`, `Majburiy qayta yuklash (admin /reload). Yuklangan telefonlar sonini qaytaradi.` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QueryFilter` connect `Community 6` to `Community 0`, `Community 2`?**
  _High betweenness centrality (0.200) - this node is a cross-community bridge._
- **Why does `Phone` connect `Community 6` to `Community 1`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Why does `recommend()` connect `Community 0` to `Community 6`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `recommend()` (e.g. with `QueryFilter` and `main()`) actually correct?**
  _`recommend()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Google Sheet (live) dan telefonlar bazasini o'qish + RAM cache (TTL).  Agar Goog`, `8 GB', '5,000,000', '5000mAh' -> int; bo'sh/xato -> None.`, `Manbadan telefonlar ro'yxatini yuklaydi (cachesiz, to'g'ridan-to'g'ri).` to the rest of the system?**
  _42 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._