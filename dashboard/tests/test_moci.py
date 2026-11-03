"""MOCI page parser tests on a snippet in the page's layout (copied 2026-11-03), no network. Run: python tests/test_moci.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import moci  # noqa: E402

PAGE = """<p class="gold-pill">أسعار يوم الاثنين 02/11/2026</p> </div> </section> <section class="sec"> <div class="wrap gold">
<div class="gold-cards"><div class="gold-card"><span class="gold-card__k">عيار 24</span><b class="gold-card__v" dir="ltr">38.680</b><small>د.ك / غرام</small></div>
<div class="gold-card"><span class="gold-card__k">عيار 22</span><b class="gold-card__v" dir="ltr">35.457</b><small>د.ك / غرام</small></div>
<div class="gold-card"><span class="gold-card__k">عيار 21</span><b class="gold-card__v" dir="ltr">33.845</b><small>د.ك / غرام</small></div>
<div class="gold-card"><span class="gold-card__k">عيار 18</span><b class="gold-card__v" dir="ltr">29.010</b><small>د.ك / غرام</small></div></div>
<h2 class="gold-h">سعر الأونصة</h2> <div class="gold-ounces"><div class="gold-oz gold-oz--gold"><span>أونصة الذهب</span><b dir="ltr">1,203.088</b><small>د.ك / أونصة</small></div>
<div class="gold-oz gold-oz--silver"><span>أونصة الفضة</span><b dir="ltr">15.409</b><small>د.ك / أونصة</small></div>
<div class="gold-oz gold-oz--platinum"><span>أونصة البلاتين</span><b dir="ltr">443.175</b><small>د.ك / أونصة</small></div></div>"""


def test_parse_page():
    p = moci.parse(PAGE)
    assert p["date"] == "2026-11-02"
    assert p["karat"] == {"24K": 38.680, "22K": 35.457, "21K": 33.845, "18K": 29.010}
    assert p["ounce"] == {"gold": 1203.088, "silver": 15.409, "platinum": 443.175}
    assert abs(p["silver_gram"] - 15.409 / moci.TROY_OZ_G) < 1e-9


def test_unreadable_or_inconsistent_page_gives_none():
    assert moci.parse("<html>maintenance</html>") is None
    assert moci.parse(PAGE.replace("1,203.088", "1,303.088")) is None  # ounce no longer matches the gram price


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"[OK] {name}")
    print("All MOCI tests passed.")
