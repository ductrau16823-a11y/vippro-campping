#!/usr/bin/env python3
"""
Test lên camp cho 1 TK cụ thể.
Profile: Đức 14/4/26_011 (genloginId: 25892793)
Account: 373-251-9645
Gmail: PierreBourbigot928@gmail.com
Project: viltrox
"""

import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from genlogin_api import start_profile, get_debugger_address, get_browser_version, connect_selenium
from camp_runner import handle_post_navigate, check_account_status
from camp_google_ads_v3 import CampaignCreator
from status_tracker import StatusTracker

# === CONFIG ===
GENLOGIN_ID = "25892790"    # Đức 14/4/26_008
ACCOUNT_ID = "544-689-3084"
GMAIL_EMAIL = "MiladCecile797@gmail.com"
PROFILE_ID = "cmnybntnm0073k0k56ida1txd"
PROFILE_NAME = "Đức 14/4/26_008"

# Campaign config tu project viltrox
CAMPAIGN_CONFIG = {
    "name": "viltrox",
    "goal": "traffic",
    "type": "search",
    "budget": "1",
    "bidding": "maximize_clicks",
    "cpc": "0.5",
    "adgroup_name": "AG_viltrox",
    "keywords": ["[viltrox]"],
    "final_url": "https://viltrox.com/?ref=hjpqijqc",
    "headlines": [
        "{Keyword:Viltrox}", "Viltrox Camera Lens", "Collection: Camera Lenses",
        "Viltrox Store", "Viltrox Official Store", "Viltrox.com",
        "Viltrox", "Official Store", "Sign Up Now",
    ],
    "descriptions": [
        "Now Viltrox has Four camera lenses covered in the lens lineup",
        "This is Viltrox official online flagship store preliminarily based on US and EU areas.",
    ],
    "target_locations": [
        "United States", "Australia", "Canada", "Germany", "France", "Italy", "Austria",
    ],
    "exclude_locations": ["Viet Nam", "California, USA"],
    "devices": ["Di động", "Máy tính"],
    "age_ranges": ["18-24", "25-34", "35-44", "45-54", "55-64"],
    "gender": "Tất cả",
}


def main():
    print(f"=== TEST CAMP: {PROFILE_NAME} / {ACCOUNT_ID} ===")
    print()

    # 1. Connect GenLogin profile
    print(f"[1] Start profile {GENLOGIN_ID}...")
    start_result = start_profile(GENLOGIN_ID)
    debugger_addr = get_debugger_address(start_result)
    browser_ver = get_browser_version(start_result)

    if not debugger_addr:
        print(f"[ERROR] Khong lay duoc debugger address!")
        print(f"Start result: {start_result}")
        return

    print(f"[OK] Debugger: {debugger_addr}")
    driver = connect_selenium(debugger_addr, browser_ver)
    print(f"[OK] Da ket noi Selenium! Title: {driver.title}")

    # 2. Navigate vao TK Ads
    cid = ACCOUNT_ID.replace("-", "")
    ads_url = f"https://ads.google.com/aw/campaigns?ocid={cid}"
    print(f"\n[2] Navigate: {ads_url}")
    driver.get(ads_url)
    time.sleep(10)
    print(f"[OK] Title: {driver.title}")

    # 3. Xu ly login + chon TK
    print(f"\n[3] Handle login + chon TK...")
    ok = handle_post_navigate(driver, GMAIL_EMAIL, PROFILE_ID, PROFILE_NAME, ACCOUNT_ID)
    if not ok:
        print(f"[ERROR] Khong vao duoc TK {ACCOUNT_ID}!")
        return
    time.sleep(3)

    # 4. Check status TK
    print(f"\n[4] Check TK status...")
    tk_status = check_account_status(driver, PROFILE_NAME, ACCOUNT_ID, None)
    print(f"[INFO] TK status: {tk_status}")
    if tk_status != "ok":
        print(f"[WARN] TK status={tk_status} — van thu len camp...")

    # 5. Chay CampaignCreator
    print(f"\n[5] Bat dau tao campaign viltrox...")
    tracker = StatusTracker()
    account_data = {
        "accountId": ACCOUNT_ID,
        "gmailEmail": GMAIL_EMAIL,
        "profileId": PROFILE_ID,
    }
    creator = CampaignCreator(driver, account_data, tracker)

    try:
        result = creator.run_campaign_flow(CAMPAIGN_CONFIG, skip_navigate=True, camp_index=1)
        if result:
            print(f"\n=== THANH CONG! Campaign 'viltrox' da publish ===")
        else:
            print(f"\n=== THAT BAI! ===")
    except Exception as e:
        print(f"\n=== LOI: {e} ===")
        import traceback
        traceback.print_exc()

    print("\n[DONE] Browser van mo — anh check thu cong.")


if __name__ == "__main__":
    main()
