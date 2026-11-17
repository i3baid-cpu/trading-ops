"""Dar Al Sabaek price parser tests on the reply read 2026-11-17, no network. Run: python tests/test_daralsabaek.py"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import daralsabaek as das  # noqa: E402

REPLY = ('{"succeeded":true,"message":"","result":{"purchaseGoldPrice":39.1294051697,"purchase22GoldPrice":35.868360542857202,'
         '"purchase21GoldPrice":34.2382295234875,"purchase18GoldPrice":29.347053877275,"sellGoldPrice":38.8344051697,'
         '"sell22GoldPrice":35.368360542857202,"sell21GoldPrice":33.6382295234875,"sell18GoldPrice":28.647053877275,'
         '"purchaseSilverPrice":0.5488430098,"sellSilverPrice":0.5038430098,"purchasePlatinumPrice":14.8723582365,'
         '"sellPlatinumPrice":14.3723582365,"updateIntervalInSeconds":15,"goldOuncePrice":3865.8400000000,'
         '"silverKiloPrice":548.8430098000,"goldPriceStatus":1,"silverPriceStatus":0},"errors":[]}')
NOW = datetime(2026, 11, 17, 12, 30, tzinfo=timezone.utc)


def _with(**kw):
    d = json.loads(REPLY)
    d["result"].update(kw)
    return json.dumps(d)


def test_parse_reply():
    p = das.parse(REPLY, NOW)
    assert p["time"] == "2026-11-17 12:30 UTC" and p["status"] == 1
    assert round(p["buy"]["24K"], 3) == 39.129 and round(p["sell"]["24K"], 3) == 38.834
    assert round(p["buy"]["21K"], 3) == 34.238 and round(p["sell"]["18K"], 3) == 28.647
    assert p["gold_oz_usd"] == 3865.84


def test_unexpected_reply_gives_none():
    assert das.parse("<html>maintenance</html>") is None
    assert das.parse('{"succeeded":false,"result":null}') is None
    assert das.parse(_with(sellGoldPrice=39.5)) is None                  # sells above its buy price
    assert das.parse(_with(purchase21GoldPrice=36.0)) is None            # 21K no longer priced by purity
    assert das.parse(_with(goldOuncePrice=1203.0)) is None               # ounce in KWD, not USD: rate outside the band


def test_only_the_price_address_is_called():
    src = open(das.__file__).read()
    assert src.count("https://") == 1 and das.PRICE_URL.endswith("/getMetalSellAndBuyPrices")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"[OK] {name}")
    print("All Dar Al Sabaek tests passed.")
