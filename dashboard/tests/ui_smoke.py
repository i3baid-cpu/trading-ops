"""Headless UI smoke test: opens every screen, exercises filters, asserts no Streamlit exception, saves screenshots.
Usage: python tests/ui_smoke.py [http://localhost:8501] [out_dir]
"""
import sys, os, time
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
out = sys.argv[2] if len(sys.argv) > 2 else "screenshots"
os.makedirs(out, exist_ok=True)
TABS = ["A · Executive Overview", "B · Performance", "C · Strategy Comparison", "D · Trade Explorer",
        "E · Risk", "F · System Health", "G · Signal Explanation"]


def settle(page, ms=1500):
    page.wait_for_timeout(ms)
    for _ in range(40):
        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
            break
        page.wait_for_timeout(250)


def assert_no_error(page, where):
    errs = page.locator('[data-testid="stException"]')
    if errs.count():
        raise SystemExit(f"[FAIL] Streamlit exception on {where}:\n{errs.first.inner_text()[:2000]}")


results = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1500, "height": 1000})
    page.goto(url, wait_until="networkidle")
    settle(page, 4000)
    assert_no_error(page, "initial load")
    assert page.get_by_text("Trading Command Center").first.is_visible()
    assert page.get_by_text("READ ONLY").first.is_visible(), "read-only banner missing"
    for i, name in enumerate(TABS):
        page.get_by_role("tab", name=name).click()
        settle(page)
        assert_no_error(page, name)
        n_charts = page.locator(".js-plotly-plot").count()
        n_tables = page.locator('[data-testid="stDataFrame"]').count()
        page.screenshot(path=f"{out}/{i:02d}_{name.split('·')[1].strip().replace(' ', '_').lower()}.png", full_page=True)
        results.append((name, n_charts, n_tables))
        print(f"[OK] {name}: {n_charts} plotly charts, {n_tables} tables")

    # Interactions: trade explorer search + row selection
    page.get_by_role("tab", name=TABS[3]).click(); settle(page)
    box = page.get_by_label("Search (id, symbol, reason, note)")
    box.fill("FT-15"); box.press("Enter"); settle(page)
    assert_no_error(page, "search")
    assert page.get_by_text("1 of 35 trade records").is_visible(), "search filter did not narrow to one trade"
    assert page.get_by_text("Trade detail · FT-15").is_visible()
    page.screenshot(path=f"{out}/10_trade_explorer_search.png", full_page=True)
    print("[OK] Trade explorer search + detail panel")
    box.fill(""); box.press("Enter"); settle(page)

    # Signal explanation: pick a Robinhood stop-out
    page.get_by_role("tab", name=TABS[6]).click(); settle(page)
    page.locator('[data-testid="stSelectbox"]', has_text="Trade or signal").locator('input').click()
    page.keyboard.type("RH-05"); page.keyboard.press("Enter"); settle(page)
    assert_no_error(page, "signal select")
    assert page.get_by_text("SELL (stop)").first.is_visible(), "stop explanation not rendered"
    page.screenshot(path=f"{out}/11_signal_rh_stop.png", full_page=True)
    print("[OK] Signal explanation for a Robinhood stop-out")

    # Sidebar filter: Freqtrade only + NY timezone
    page.get_by_text("America/New_York").click(); settle(page)
    rb = page.get_by_text("Robinhood", exact=True)
    # remove Robinhood from the Systems multiselect
    page.locator('[data-testid="stSidebar"] button[aria-label="Remove Robinhood"]').first.click()
    settle(page)
    assert_no_error(page, "system filter")
    page.get_by_role("tab", name=TABS[1]).click(); settle(page)
    page.screenshot(path=f"{out}/12_performance_freqtrade_only_nyt.png", full_page=True)
    print("[OK] Sidebar filters (system removed, timezone switched)")
    b.close()

print("\nAll screens rendered without exceptions.")
for n, c, t in results:
    print(f"  {n:<28} charts={c:<2} tables={t}")
