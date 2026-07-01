"""Botni ishga tushirish uchun qulay entrypoint: python run.py (repo ildizidan)."""
from __future__ import annotations

import asyncio

from bot.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
