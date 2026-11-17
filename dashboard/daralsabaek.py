"""Dar Al Sabaek gold prices: what a Kuwaiti buyer actually pays and gets, in KWD per gram. Read only, standard library
only, so the logger (scripts/das_log.py) can run outside the dashboard image.

Dar Al Sabaek is a Kuwaiti gold dealer; its website loads live buy and sell prices for 24K, 22K, 21K and 18K from one
price address that needs no login (the site refreshes it every 15 seconds). Abdullah chose it on 17 Nov 2026 as the
gold reference instead of MOCI, whose page blocks scripts since 10 Nov. Only PRICE_URL is ever called; the same server
also takes customer orders, which this module must never reference (tests/test_data.py checks it). The address is the
dealer's own, not a published service, so it can change without notice: anything unexpected gives None and callers show
Not available. Gold only; silver stays on the international price.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

PRICE_URL = "https://api.daralsabaek.com/api/goldAndFundBalance/getMetalSellAndBuyPrices"
TROY_OZ_G = 31.1034768
KARATS = {"24K": 24, "22K": 22, "21K": 21, "18K": 18}
FIELDS = {"24K": "", "22K": "22", "21K": "21", "18K": "18"}  # purchase{n}GoldPrice / sell{n}GoldPrice, 24K has no number
FX_RANGE = (0.25, 0.35)  # same band as metals.FX_RANGE: their KWD price over their USD ounce must look like a dinar rate
MAX_SPREAD = 0.05


def parse(text: str, now: datetime | None = None) -> dict | None:
    try:
        r = json.loads(text)["result"]
        buy = {k: float(r[f"purchase{f}GoldPrice"]) for k, f in FIELDS.items()}
        sell = {k: float(r[f"sell{f}GoldPrice"]) for k, f in FIELDS.items()}
        oz = float(r["goldOuncePrice"])
    except (ValueError, KeyError, TypeError):
        return None
    if min(sell.values()) <= 0 or any(not 0 <= buy[k] / sell[k] - 1 <= MAX_SPREAD for k in KARATS):
        return None  # sell above buy, or a spread no dealer quotes: unreadable, never guess
    if any(abs(buy[k] / (buy["24K"] * n / 24) - 1) > 0.01 for k, n in KARATS.items()):
        return None  # karats no longer priced by purity
    fx = (buy["24K"] + sell["24K"]) / 2 * TROY_OZ_G / oz if oz > 0 else 0
    if not FX_RANGE[0] < fx < FX_RANGE[1]:
        return None
    now = now or datetime.now(timezone.utc)
    return {"time": f"{now:%Y-%m-%d %H:%M} UTC", "buy": buy, "sell": sell, "gold_oz_usd": oz, "status": r.get("goldPriceStatus")}


def fetch(timeout: float = 10) -> tuple[dict | None, str]:
    try:
        req = urllib.request.Request(PRICE_URL, headers={"User-Agent": "Mozilla/5.0 (trading-ops read only)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as e:  # network, TLS, HTTP error
        return None, f"Dar Al Sabaek prices not reachable: {e}"
    p = parse(text)
    return (p, f"Dar Al Sabaek live prices, read {p['time']}") if p else (None, "Dar Al Sabaek reply not recognised; no dealer price shown")
