# Texnomart JSON Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Texnomart searches fast by serving recommendations from a local JSON cache instead of scraping the live site for every user query.

**Architecture:** Add a focused `texnomart_cache.py` module that serializes `Phone` records to JSON with source URLs preserved. `sheets.py` will route Texnomart loads through this cache. Fresh or stale cache data returns immediately; stale cache triggers a background refresh so user requests do not wait on the site.

**Tech Stack:** Python standard library (`json`, `threading`, `time`, `dataclasses`, `pathlib`), existing `Phone` dataclass, existing scraper and tests.

---

### Task 1: Add Cache Module

**Files:**
- Create: `texnomart_cache.py`
- Test: `test_texnomart_cache.py`

- [ ] **Step 1: Write tests for cache read/write and stale fallback**

Create tests that write `Phone` objects to a temporary cache path, read them back, verify `detail_url` and `source_label` survive, and verify stale cache returns immediately while starting a refresh.

- [ ] **Step 2: Implement `texnomart_cache.py`**

Expose `load_cached_or_refresh(...)` and `refresh_cache(...)`. Use JSON shape:

```json
{"generated_at": 123.0, "phones": [{"brand": "Oppo", "detail_url": "...", "source_label": "texno"}]}
```

- [ ] **Step 3: Verify cache tests pass**

Run: `python3 test_texnomart_cache.py`

### Task 2: Integrate Cache With Sheets

**Files:**
- Modify: `config.py`
- Modify: `sheets.py`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `SERVER_RUN.txt`
- Test: `test_texnomart_scraper.py`

- [ ] **Step 1: Add config**

Add `TEXNOMART_CACHE_PATH` and `TEXNOMART_CACHE_TTL`.

- [ ] **Step 2: Route Texnomart source through cache**

Make `_load_from_texnomart()` call `texnomart_cache.load_cached_or_refresh`.

- [ ] **Step 3: Update docs**

Document that source links are preserved and that cache refresh controls live in `.env`.

- [ ] **Step 4: Verify focused tests**

Run:

```bash
python3 test_texnomart_cache.py
python3 test_texnomart_scraper.py
python3 -m py_compile config.py sheets.py texnomart_cache.py texnomart_scraper.py
```
