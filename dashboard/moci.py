"""Kuwait Ministry of Commerce and Industry (MOCI) gold reference prices. Read only, standard library only, so the
daily logger (scripts/moci_log.py) can run outside the dashboard image.

The page gives one set of prices per business day, taken from the Central Bank of Kuwait bulletin: KWD per gram for
24K, 22K, 21K and 18K, and KWD per ounce for gold, silver and platinum. They are metal only, without workmanship or
shop margin, which is what Kuwaiti shops price against. The values are in the page's HTML; if its layout changes or
the numbers disagree with each other, parse() returns None and callers show Not available.
"""
from __future__ import annotations

import re
import urllib.request
from datetime import datetime

URL = "https://moci.gov.kw/MociSite/gold-prices/index.html"
TROY_OZ_G = 31.1034768


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse(html: str) -> dict | None:
    d = re.search(r'class="gold-pill">[^<]*?(\d{2}/\d{2}/\d{4})', html)
    cards = re.findall(r'class="gold-card__k">[^<]*?(\d{2})\s*</span>\s*<b class="gold-card__v"[^>]*>([\d.,]+)</b>', html)
    oz = dict(re.findall(r'class="gold-oz gold-oz--(gold|silver|platinum)">.*?<b[^>]*>([\d.,]+)</b>', html, flags=re.S))
    if not d or not cards or "gold" not in oz:
        return None
    karat = {f"{k}K": _num(v) for k, v in cards}
    ounce = {k: _num(v) for k, v in oz.items()}
    if "24K" not in karat or abs(ounce["gold"] / TROY_OZ_G / karat["24K"] - 1) > 0.005:
        return None  # the page's own gram and ounce prices disagree: treat as unreadable, never guess
    return {"date": datetime.strptime(d.group(1), "%d/%m/%Y").date().isoformat(), "karat": karat, "ounce": ounce,
            "silver_gram": ounce["silver"] / TROY_OZ_G if "silver" in ounce else None}


def fetch(timeout: float = 10) -> tuple[dict | None, str]:
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (trading-ops read only)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:  # network, TLS, HTTP error
        return None, f"MOCI page not reachable: {e}"
    p = parse(html)
    return (p, f"MOCI gold prices page, prices of {p['date']}") if p else (None, "MOCI page layout not recognised; no reference price shown")
