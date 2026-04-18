#!/usr/bin/env python3
"""
Test click "Page view" card tren trang Choose conversion goals.
Yeu cau: Profile GenLogin "Đức 14/4/26_009" dang chay, da o trang chon goal.
"""

import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from selenium.webdriver.common.by import By
from genlogin_api import (
    start_profile,
    get_debugger_address,
    get_browser_version,
    connect_selenium,
)

GENLOGIN_ID = "25892791"
ACCOUNT_ID = "785-722-4547"

PV_XPATHS = [
    "//conversion-goal-card[.//*[@id='PAGE_VIEW']]",
    "//conversion-goal-card[.//material-icon[@id='PAGE_VIEW']]//button[@role='radio']",
    "//button[@role='radio'][.//material-icon[@id='PAGE_VIEW']]",
    "//button[@role='radio'][.//div[contains(@class, 'title') and contains(text(), 'Page view')]]",
    "//conversion-goal-card[.//div[contains(@class, 'title') and contains(text(), 'Page view')]]//button",
    "//conversion-goal-card[.//div[contains(text(), 'Page view')]]//button",
    "//conversion-goal-card[.//div[contains(text(), 'Page view')]]",
]


def main():
    print(f"[1] Lay debugger address cho profile {GENLOGIN_ID}...")
    start_result = start_profile(GENLOGIN_ID)
    debugger = get_debugger_address(start_result)
    browser_ver = get_browser_version(start_result)
    if not debugger:
        print(f"[ERROR] Khong lay duoc debugger address")
        print(f"Start result: {start_result}")
        return
    print(f"[OK] Debugger: {debugger}")

    print(f"\n[3] Connect Selenium...")
    driver = connect_selenium(debugger, browser_ver)
    print(f"[OK] Current tab: {driver.title} | {driver.current_url}")

    print(f"\n[3b] Scan {len(driver.window_handles)} tab, tim tab ads.google.com...")
    found_ads = False
    for h in driver.window_handles:
        driver.switch_to.window(h)
        url = driver.current_url
        print(f"     - {driver.title[:40]} | {url[:80]}")
        if "ads.google.com" in url:
            found_ads = True
            print(f"     -> Switch sang tab nay")
            break

    # Lay ocid that tu URL hien tai (ocid != accountId)
    import re
    cur_url = driver.current_url
    m = re.search(r"[?&]ocid=(\d+)", cur_url)
    if not m:
        print(f"[ERROR] Khong parse duoc ocid tu URL: {cur_url}")
        return
    ocid = m.group(1)
    print(f"     ocid that: {ocid}")

    new_camp_url = f"https://ads.google.com/aw/campaigns/new?ocid={ocid}"
    print(f"\n[3c] Navigate: {new_camp_url}")
    driver.get(new_camp_url)
    time.sleep(5)

    print(f"\n[3d] Cho conversion-goal-card xuat hien (toi da 60s)...")
    deadline = time.time() + 60
    at_goal_picker = False
    while time.time() < deadline:
        cards = driver.find_elements(By.XPATH, "//conversion-goal-card")
        if cards:
            at_goal_picker = True
            print(f"     [OK] Tim thay {len(cards)} conversion-goal-card")
            break
        time.sleep(2)

    if not at_goal_picker:
        print(f"[ERROR] Khong thay conversion-goal-card")
        print(f"        URL: {driver.current_url}")
        print(f"        Title: {driver.title}")
        return

    print(f"\n[4] Scan PV_XPATHS (khong click), xem selector nao match...")
    matches = []
    for i, xp in enumerate(PV_XPATHS, 1):
        try:
            els = driver.find_elements(By.XPATH, xp)
            visible = [e for e in els if e.is_displayed()]
            print(f"  [{i}] {len(els)} el, {len(visible)} visible | {xp[:80]}")
            if visible and not matches:
                matches.append((i, xp, visible[0]))
        except Exception as e:
            print(f"  [{i}] ERROR: {e}")

    if not matches:
        print(f"\n[FAIL] Khong selector nao match — anh check lai trang dang o dau")
        return

    idx, xp, el = matches[0]
    print(f"\n[5] Selector #{idx} match — scroll + click:")
    print(f"    {xp}")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", el)
    time.sleep(0.5)
    try:
        el.click()
        print(f"[OK] Da click bang element.click()")
    except Exception as e:
        print(f"[WARN] element.click() fail: {e}")
        print(f"       Thu js_click...")
        driver.execute_script("arguments[0].click()", el)
        print(f"[OK] Da click bang js_click")

    time.sleep(2)
    print(f"\n[6] Sau khi click — URL: {driver.current_url}")
    print(f"\n[DONE] Browser van mo, anh tu check xem Page view da duoc chon chua.")


if __name__ == "__main__":
    main()
