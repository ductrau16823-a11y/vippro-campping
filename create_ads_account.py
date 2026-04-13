#!/usr/bin/env python3
"""
Len camp tren cac TK Google Ads co san (verified).
Flow: Lay N TK tu DB -> Mo GenLogin -> Navigate vao tung TK Ads -> Cho anh huong dan tiep.
"""

import sys
import time
import traceback
from collections import OrderedDict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from genlogin_api import (
    start_profile,
    stop_profile,
    get_debugger_address,
    connect_selenium,
    get_browser_version,
)
from db_helpers import _connect
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ADS_SELECT_ACCOUNT_URL = "https://ads.google.com/nav/selectaccount"

# Mapping campaign type tu DB -> data-value tren Google Ads UI
CAMPAIGN_TYPE_MAP = {
    "search": "SEARCH",
    "performance_max": "UBERVERSAL",
    "demand_gen": "OWNED_AND_OPERATED",
    "display": "DISPLAY",
    "shopping": "SHOPPING",
    "video": "VIDEO",
    "app": "MULTIPLE",
}


def get_2fa_key(profile_id):
    """Lay twoFactorKey tu Gmail thong qua Profile."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT g.twoFactorKey
            FROM Profile p
            JOIN Gmail g ON p.gmailId = g.id
            WHERE p.id = ?
        """, (profile_id,))
        row = cur.fetchone()
        return row["twoFactorKey"] if row and row["twoFactorKey"] else None
    finally:
        conn.close()


def generate_totp(secret):
    """Generate ma TOTP tu secret key."""
    import pyotp
    totp = pyotp.TOTP(secret)
    return totp.now()


def handle_2fa(driver, profile_id):
    """Xu ly 2FA: switch sang window moi, dien ma, switch lai."""
    original_window = driver.current_window_handle
    all_windows = driver.window_handles

    # Tim window 2FA (window moi, khong phai window hien tai)
    target_window = None
    for w in all_windows:
        if w != original_window:
            driver.switch_to.window(w)
            time.sleep(1)
            try:
                driver.find_element(By.CSS_SELECTOR, "input#totpPin")
                target_window = w
                break
            except Exception:
                continue

    if not target_window:
        # Co the 2FA o cung window (tab moi hoac iframe)
        driver.switch_to.window(original_window)
        try:
            driver.find_element(By.CSS_SELECTOR, "input#totpPin")
            target_window = original_window
        except Exception:
            print(f"[!] Khong tim thay trang 2FA")
            return False

    print(f"[*] Tim thay trang 2FA, dang lay ma...")

    # Lay secret key tu DB
    secret = get_2fa_key(profile_id)
    if not secret:
        print(f"[!] Khong co twoFactorKey trong DB!")
        driver.switch_to.window(original_window)
        return False

    # Generate va dien ma
    code = generate_totp(secret)
    print(f"[*] Nhap ma 2FA: {code}")

    totp_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input#totpPin"))
    )
    totp_input.click()
    time.sleep(0.3)
    totp_input.send_keys(code)
    time.sleep(1)

    # Click Next
    next_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#totpNext button"))
    )
    next_btn.click()
    time.sleep(5)
    print(f"[OK] 2FA thanh cong")

    # Switch lai window goc
    if target_window != original_window:
        try:
            driver.switch_to.window(original_window)
        except Exception:
            # Window 2FA co the da dong, lay window con lai
            for w in driver.window_handles:
                driver.switch_to.window(w)
                break
    time.sleep(3)
    return True


def dismiss_confirm_popup(driver):
    """Check va tat popup 'Confirm it's you' neu xuat hien."""
    try:
        confirm_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH,
                "//material-dialog//material-button[contains(@class, 'setup')]"))
        )
        confirm_btn.click()
        time.sleep(3)
        print(f"[OK] Da click Confirm")
        return True
    except Exception:
        return False


def check_confirm_and_2fa(driver, profile_id):
    """Check popup Confirm + 2FA. Goi truoc moi buoc chinh."""
    if dismiss_confirm_popup(driver):
        time.sleep(3)
        handle_2fa(driver, profile_id)


def get_project_by_id(project_id):
    """Lay thong tin project tu DB theo id."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM Project WHERE id = ?", (project_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_verified_accounts(limit):
    """Lay N TK Ads verified, kem thong tin profile."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.accountId, a.profileId, p.id AS profileDbId,
                   p.name AS profileName, p.genloginId, g.email
            FROM AdsAccount a
            JOIN Profile p ON a.profileId = p.id
            LEFT JOIN Gmail g ON p.gmailId = g.id
            WHERE a.status = 'verified'
              AND p.genloginId IS NOT NULL
              AND p.genloginId != ''
            ORDER BY a.createdAt
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def group_by_profile(accounts):
    """Gom TK theo genloginId de mo 1 profile, chay nhieu TK."""
    grouped = OrderedDict()
    for acc in accounts:
        gid = acc["genloginId"]
        if gid not in grouped:
            grouped[gid] = {
                "genloginId": gid,
                "profileDbId": acc["profileDbId"],
                "profileName": acc["profileName"],
                "email": acc["email"],
                "accounts": [],
            }
        grouped[gid]["accounts"].append(acc["accountId"])
    return list(grouped.values())


def run(limit, project_id):
    print("=" * 60)
    print("   LEN CAMP - NAVIGATE VAO TK ADS")
    print("=" * 60)

    # 1. Lay project tu DB
    project = get_project_by_id(project_id)
    if not project:
        print(f"[!] Khong tim thay project voi id: {project_id}")
        return

    project_name = project.get("name", "")
    print(f"\n[*] Du an: {project_name}")

    # 2. Lay TK tu DB
    accounts = get_verified_accounts(limit)
    if not accounts:
        print("[!] Khong co TK Ads verified nao trong DB.")
        return

    if len(accounts) < limit:
        print(f"[!] Chi co {len(accounts)} TK verified (yeu cau {limit}).")

    groups = group_by_profile(accounts)

    print(f"\n[*] {len(accounts)} TK Ads tren {len(groups)} profile:")
    for g in groups:
        ids = ", ".join(g["accounts"])
        print(f"  {g['profileName']} ({g['email']}): {ids}")
    print()

    # 2-3. Loop tung profile -> tung TK
    done = 0
    current_genlogin = None
    driver = None

    try:
        for group in groups:
            genlogin_id = group["genloginId"]
            profile_name = group["profileName"]
            email = group["email"]

            # Mo GenLogin profile
            if current_genlogin != genlogin_id:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    try:
                        stop_profile(current_genlogin)
                    except Exception:
                        pass

                print(f"\n{'=' * 50}")
                print(f"Mo profile: {profile_name} | {email}")
                print(f"{'=' * 50}")

                print(f"[*] Start GenLogin profile {genlogin_id}...")
                start_result = start_profile(genlogin_id)
                debugger_addr = get_debugger_address(start_result)
                browser_ver = get_browser_version(start_result)

                if not debugger_addr:
                    print(f"[!] Khong lay duoc debugger address, skip profile!")
                    driver = None
                    current_genlogin = None
                    continue

                print(f"[*] Ket noi Selenium...")
                driver = connect_selenium(debugger_addr, browser_ver)
                print(f"[OK] Ket noi thanh cong")
                current_genlogin = genlogin_id

                # Vao trang chon TK truoc
                print(f"[*] Navigate vao {ADS_SELECT_ACCOUNT_URL}...")
                driver.get(ADS_SELECT_ACCOUNT_URL)
                time.sleep(5)

            if not driver:
                continue

            # Click tung TK Ads tren trang selectaccount
            for acc_idx, account_id in enumerate(group["accounts"]):
                current = acc_idx + 1 + sum(len(g["accounts"]) for g in groups[:groups.index(group)])

                print(f"\n[{current}/{len(accounts)}] TK: {account_id}")

                # Quay lai trang chon TK (tu con thu 2 tro di)
                if current > 1:
                    print(f"[*] Quay lai trang chon TK...")
                    driver.get(ADS_SELECT_ACCOUNT_URL)
                    time.sleep(5)

                # Tim va click vao TK theo account ID
                print(f"[*] Tim va click TK {account_id}...")
                try:
                    # Tim element chua account ID (format XXX-XXX-XXXX)
                    xpath = f"//*[contains(text(), '{account_id}')]"
                    el = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    el.click()
                    time.sleep(5)

                    print(f"[OK] Da click vao TK {account_id}")
                    print(f"[OK] URL: {driver.current_url}")

                    check_confirm_and_2fa(driver, group["profileDbId"])

                    # Click nut Create (dau +)
                    print(f"[*] Tim nut Create (dau +)...")
                    create_btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "uber-create material-fab"))
                    )
                    create_btn.click()
                    time.sleep(3)
                    print(f"[OK] Da click nut Create")

                    # Click "Campaign" trong menu dropdown
                    print(f"[*] Chon Campaign...")
                    campaign_item = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//material-select-item[@aria-label='Campaign']"))
                    )
                    campaign_item.click()
                    time.sleep(5)
                    print(f"[OK] Da chon Campaign")

                    # Chon "Create a campaign without guidance"
                    print(f"[*] Chon 'Create a campaign without guidance'...")
                    no_objective = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//dynamic-component[@data-value='No objective']"))
                    )
                    no_objective.click()
                    time.sleep(3)
                    print(f"[OK] Da chon No objective")

                    # Chon campaign type (mac dinh Search, sau doc tu DB)
                    campaign_type = "search"  # TODO: doc tu DB khi anh them field
                    data_value = CAMPAIGN_TYPE_MAP.get(campaign_type, "SEARCH")
                    print(f"[*] Chon campaign type: {campaign_type} ({data_value})...")
                    type_card = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            f"//dynamic-component[@data-value='{data_value}']"))
                    )
                    type_card.click()
                    time.sleep(3)
                    print(f"[OK] Da chon {campaign_type}")

                    # Tick "Website visits"
                    print(f"[*] Tick 'Website visits'...")
                    website_visits = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//material-checkbox[.//div[contains(text(), 'Website visits')]]"))
                    )
                    website_visits.click()
                    time.sleep(2)
                    print(f"[OK] Da tick Website visits")

                    # Click Continue
                    print(f"[*] Click Continue...")
                    continue_btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "button.btn-yes"))
                    )
                    continue_btn.click()
                    time.sleep(5)
                    print(f"[OK] Da click Continue")

                    # Chon goal "Page view"
                    print(f"[*] Chon goal 'Page view'...")
                    page_view = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//conversion-goal-card[.//div[contains(@class, 'title') and contains(text(), 'Page view')]]//button"))
                    )
                    page_view.click()
                    time.sleep(3)
                    print(f"[OK] Da chon Page view")

                    # Dien Campaign name = ten du an tu DB
                    print(f"[*] Dien Campaign name: {project_name}...")
                    name_input = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR,
                            "campaign-name-view input[aria-label='Campaign name']"))
                    )
                    name_input.click()
                    time.sleep(0.5)
                    name_input.send_keys(Keys.CONTROL, "a")
                    time.sleep(0.2)
                    name_input.send_keys(Keys.DELETE)
                    time.sleep(0.2)
                    name_input.send_keys(project_name)
                    time.sleep(2)
                    print(f"[OK] Da dien Campaign name: {project_name}")

                    # Bo tick "Turn on enhanced conversions"
                    print(f"[*] Bo tick 'Enhanced conversions'...")
                    ec_checkbox = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//enhanced-conversions-view//material-checkbox[@aria-checked='true']"))
                    )
                    ec_checkbox.click()
                    time.sleep(2)
                    print(f"[OK] Da bo tick Enhanced conversions")

                    # Click Continue
                    print(f"[*] Click Continue...")
                    continue_btn3 = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "button.btn-yes"))
                    )
                    continue_btn3.click()
                    time.sleep(5)
                    print(f"[OK] Da click Continue")

                    check_confirm_and_2fa(driver, group["profileDbId"])

                    # === BUOC BIDDING ===
                    # Doc bidding va cpc tu DB
                    bidding = project.get("bidding", "").lower() if project.get("bidding") else ""
                    cpc = project.get("cpc") or project.get("bid_value")

                    if "click" in bidding:
                        # Doi dropdown tu Conversions sang Clicks
                        print(f"[*] Doi Bidding focus sang Clicks...")
                        bidding_dropdown = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                "#metric-dropdown dropdown-button"))
                        )
                        bidding_dropdown.click()
                        time.sleep(2)

                        clicks_option = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//material-select-item[.//span[contains(text(), 'Clicks')]]"))
                        )
                        clicks_option.click()
                        time.sleep(3)
                        print(f"[OK] Da chon Clicks")

                        # Dien max CPC neu co
                        if cpc:
                            print(f"[*] Tick 'Set a maximum cost per click bid limit'...")
                            cpc_checkbox = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH,
                                    "//material-checkbox[contains(@class, 'target-cpa-checkbox')]"))
                            )
                            cpc_checkbox.click()
                            time.sleep(2)

                            print(f"[*] Dien max CPC: {cpc}...")
                            cpc_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH,
                                    "//input[contains(@aria-label, 'bid limit') or contains(@aria-label, 'Maximum CPC') or contains(@aria-label, 'cost per click')]"))
                            )
                            cpc_input.click()
                            time.sleep(0.3)
                            cpc_input.send_keys(Keys.CONTROL, "a")
                            time.sleep(0.2)
                            cpc_input.send_keys(Keys.DELETE)
                            time.sleep(0.2)
                            cpc_input.send_keys(str(cpc))
                            time.sleep(2)
                            print(f"[OK] Da dien max CPC: {cpc}")

                    check_confirm_and_2fa(driver, group["profileDbId"])

                    # === BUOC CAMPAIGN SETTINGS ===
                    # Click Next de sang Campaign Settings
                    print(f"[*] Click Next sang Campaign Settings...")
                    next_btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//material-button[.//span[contains(text(), 'Next')]]"))
                    )
                    next_btn.click()
                    time.sleep(5)
                    print(f"[OK] Da sang Campaign Settings")

                    # Bo tick Google Search Partners Network
                    print(f"[*] Bo tick 'Google Search Partners Network'...")
                    search_partners_cb = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-checkbox.search-checkbox[aria-checked='true']"))
                    )
                    search_partners_cb.click()
                    time.sleep(1)
                    print(f"[OK] Da bo tick Search Partners")

                    # Bo tick Google Display Network
                    print(f"[*] Bo tick 'Google Display Network'...")
                    display_cb = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-checkbox.display-checkbox[aria-checked='true']"))
                    )
                    display_cb.click()
                    time.sleep(1)
                    print(f"[OK] Da bo tick Display Network")

                    # Locations: chon "Enter another location"
                    print(f"[*] Chon 'Enter another location'...")
                    enter_location = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//material-radio[.//div[contains(text(), 'Enter another location')]]"))
                    )
                    enter_location.click()
                    time.sleep(2)
                    print(f"[OK] Da chon Enter another location")

                    # Click "Advanced search"
                    print(f"[*] Click 'Advanced search'...")
                    advanced_search = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//material-button[.//div[contains(text(), 'Advanced search')]]"))
                    )
                    advanced_search.click()
                    time.sleep(3)
                    print(f"[OK] Da click Advanced search")

                    # Tick "Add locations in bulk"
                    print(f"[*] Tick 'Add locations in bulk'...")
                    bulk_cb = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//material-checkbox[contains(@class, 'bulk-locations-checkbox')]"))
                    )
                    bulk_cb.click()
                    time.sleep(2)
                    print(f"[OK] Da tick bulk locations")

                    # Doc target_locations va exclude_locations tu DB
                    target_locs = project.get("target_locations", "") or ""
                    exclude_locs = project.get("exclude_locations", "") or ""

                    # Target locations
                    if target_locs:
                        # Chuyen pipe-separated sang xuong dong
                        target_text = target_locs.replace("|", "\n")
                        print(f"[*] Dien target locations: {target_locs}...")

                        loc_input = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH,
                                "//advanced-geopicker-editor//textarea | //advanced-geopicker-editor//input[@role='combobox']"))
                        )
                        loc_input.click()
                        time.sleep(0.5)
                        loc_input.send_keys(Keys.CONTROL, "a")
                        time.sleep(0.2)
                        loc_input.send_keys(Keys.DELETE)
                        time.sleep(0.2)
                        loc_input.send_keys(target_text)
                        time.sleep(2)

                        # Click Search
                        print(f"[*] Click Search...")
                        search_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//material-button[.//div[contains(text(), 'Search')] or .//span[contains(text(), 'Search')]]"))
                        )
                        search_btn.click()
                        time.sleep(5)

                        # Click "Target all"
                        print(f"[*] Click 'Target all'...")
                        target_all_btn = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                "material-button.add-all"))
                        )
                        target_all_btn.click()
                        time.sleep(3)
                        print(f"[OK] Da Target all")

                    # Exclude locations
                    if exclude_locs:
                        exclude_text = exclude_locs.replace("|", "\n")
                        print(f"[*] Dien exclude locations: {exclude_locs}...")

                        loc_input = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH,
                                "//advanced-geopicker-editor//textarea | //advanced-geopicker-editor//input[@role='combobox']"))
                        )
                        loc_input.click()
                        time.sleep(0.5)
                        loc_input.send_keys(Keys.CONTROL, "a")
                        time.sleep(0.2)
                        loc_input.send_keys(Keys.DELETE)
                        time.sleep(0.2)
                        loc_input.send_keys(exclude_text)
                        time.sleep(2)

                        # Click Search
                        print(f"[*] Click Search...")
                        search_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//material-button[.//div[contains(text(), 'Search')] or .//span[contains(text(), 'Search')]]"))
                        )
                        search_btn.click()
                        time.sleep(5)

                        # Click "Exclude all"
                        print(f"[*] Click 'Exclude all'...")
                        exclude_all_btn = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR,
                                "material-button.exclude-all"))
                        )
                        exclude_all_btn.click()
                        time.sleep(3)
                        print(f"[OK] Da Exclude all")

                    # Click Save
                    print(f"[*] Click Save...")
                    save_btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-yes-no-buttons .btn-yes"))
                    )
                    save_btn.click()
                    time.sleep(5)
                    print(f"[OK] Da Save locations")

                    # === LANGUAGES: xoa English -> tu dong All languages ===
                    print(f"[*] Xoa chip English -> All languages...")
                    try:
                        english_remove = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//language-selector//material-chip//div[@aria-label='English remove']"))
                        )
                        english_remove.click()
                        time.sleep(2)
                        print(f"[OK] Da xoa English -> All languages")
                    except Exception:
                        print(f"[!] Khong tim thay chip English, co the da la All languages")

                    # Click Next sang buoc tiep
                    print(f"[*] Click Next...")
                    next_btn2 = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-button.button-next"))
                    )
                    next_btn2.click()
                    time.sleep(5)
                    print(f"[OK] Da click Next")

                    # === AI Max: skip, click Next luon ===
                    print(f"[*] Skip AI Max, click Next...")
                    next_btn3 = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-button.button-next"))
                    )
                    next_btn3.click()
                    time.sleep(5)
                    print(f"[OK] Da skip AI Max")

                    # === Keyword and asset generation: skip ===
                    print(f"[*] Skip Keyword and asset generation...")
                    skip_btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-button.button-skip"))
                    )
                    skip_btn.click()
                    time.sleep(5)
                    print(f"[OK] Da skip Keyword and asset generation")

                    check_confirm_and_2fa(driver, group["profileDbId"])

                    # === KEYWORDS AND ADS ===
                    # 1. Dien keywords vao textarea
                    ads_key = project.get("ads_key", "") or ""
                    if ads_key:
                        keywords_text = ads_key.replace("|", "\n")
                        print(f"[*] Dien keywords: {ads_key[:50]}...")
                        kw_textarea = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH,
                                "//keyword-editor[contains(@minerva-id, 'keywords-editor-box')]//textarea"))
                        )
                        kw_textarea.click()
                        time.sleep(0.5)
                        kw_textarea.send_keys(keywords_text)
                        time.sleep(2)
                        print(f"[OK] Da dien keywords")

                    # 2. Dien Final URL (phan Ads)
                    link1 = project.get("link1", "") or ""
                    if link1:
                        print(f"[*] Dien Final URL: {link1}...")
                        final_url_input = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH,
                                "//final-url-input//input[@aria-label='Final URL']"))
                        )
                        final_url_input.click()
                        time.sleep(0.5)
                        final_url_input.send_keys(link1)
                        time.sleep(3)
                        print(f"[OK] Da dien Final URL")

                    # 3. Dien Headlines
                    headlines = project.get("headlines", "") or ""
                    if headlines:
                        headline_list = [h.strip() for h in headlines.split("|") if h.strip()]
                        print(f"[*] Dien {len(headline_list)} headlines...")
                        headline_inputs = driver.find_elements(By.XPATH,
                            "//section[contains(@class, 'headline-section')]//input[@aria-label='Headline' or @aria-labelledby]")
                        for i, text in enumerate(headline_list):
                            if i < len(headline_inputs):
                                headline_inputs[i].click()
                                time.sleep(0.3)
                                headline_inputs[i].send_keys(text)
                                time.sleep(0.5)
                            else:
                                # Click nut + Headline de them o moi
                                try:
                                    add_headline_btn = driver.find_element(By.XPATH,
                                        "//section[contains(@class, 'headline-section')]//material-button[.//material-icon[@icon='add']]")
                                    add_headline_btn.click()
                                    time.sleep(1)
                                    new_inputs = driver.find_elements(By.XPATH,
                                        "//section[contains(@class, 'headline-section')]//input[@aria-label='Headline' or @aria-labelledby]")
                                    if len(new_inputs) > i:
                                        new_inputs[i].click()
                                        time.sleep(0.3)
                                        new_inputs[i].send_keys(text)
                                        time.sleep(0.5)
                                except Exception:
                                    print(f"[!] Khong the them headline thu {i+1}")
                        print(f"[OK] Da dien {min(len(headline_list), 15)} headlines")

                    # 4. Dien Descriptions
                    descriptions = project.get("descriptions", "") or ""
                    if descriptions:
                        desc_list = [d.strip() for d in descriptions.split("|") if d.strip()]
                        print(f"[*] Dien {len(desc_list)} descriptions...")
                        desc_textareas = driver.find_elements(By.XPATH,
                            "//section[contains(@class, 'description-section')]//textarea[@aria-label='Description']")
                        for i, text in enumerate(desc_list):
                            if i < len(desc_textareas):
                                desc_textareas[i].click()
                                time.sleep(0.3)
                                desc_textareas[i].send_keys(text)
                                time.sleep(0.5)
                            else:
                                try:
                                    add_desc_btn = driver.find_element(By.XPATH,
                                        "//section[contains(@class, 'description-section')]//material-button[.//material-icon[@icon='add']]")
                                    add_desc_btn.click()
                                    time.sleep(1)
                                    new_textareas = driver.find_elements(By.XPATH,
                                        "//section[contains(@class, 'description-section')]//textarea[@aria-label='Description']")
                                    if len(new_textareas) > i:
                                        new_textareas[i].click()
                                        time.sleep(0.3)
                                        new_textareas[i].send_keys(text)
                                        time.sleep(0.5)
                                except Exception:
                                    print(f"[!] Khong the them description thu {i+1}")
                        print(f"[OK] Da dien {min(len(desc_list), 4)} descriptions")

                    # 5. Click Next
                    print(f"[*] Click Next...")
                    next_btn4 = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-button.button-next"))
                    )
                    next_btn4.click()
                    time.sleep(5)
                    print(f"[OK] Da click Next")

                    check_confirm_and_2fa(driver, group["profileDbId"])

                    # === BUDGET ===
                    budget = project.get("budget", "") or ""
                    if budget:
                        # Chon "Set custom budget"
                        print(f"[*] Chon 'Set custom budget'...")
                        custom_budget_radio = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//proactive-budget-recommendation-picker//material-radio[.//div[contains(text(), 'Set custom budget')]]"))
                        )
                        custom_budget_radio.click()
                        time.sleep(2)
                        print(f"[OK] Da chon Set custom budget")

                        # Dien so tien
                        print(f"[*] Dien budget: {budget}...")
                        budget_input = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH,
                                "//budget-base-edit//input[@aria-label='Set your average daily budget for this campaign']"))
                        )
                        budget_input.click()
                        time.sleep(0.5)
                        budget_input.send_keys(Keys.CONTROL, "a")
                        time.sleep(0.2)
                        budget_input.send_keys(Keys.DELETE)
                        time.sleep(0.2)
                        budget_input.send_keys(str(budget))
                        time.sleep(2)
                        print(f"[OK] Da dien budget: {budget}")

                    # Click Next sang Review
                    print(f"[*] Click Next...")
                    next_btn5 = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,
                            "material-button.button-next"))
                    )
                    next_btn5.click()
                    time.sleep(5)
                    print(f"[OK] Da click Next")

                    check_confirm_and_2fa(driver, group["profileDbId"])

                    # === REVIEW ===
                    print(f"[*] Dang o trang Review...")

                    # Thu Publish, neu co loi Google se bao
                    for publish_attempt in range(3):
                        check_confirm_and_2fa(driver, group["profileDbId"])

                        print(f"[*] Click 'Publish campaign' (lan {publish_attempt + 1})...")
                        publish_btn = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//material-button[contains(@class, 'button-next')]//span[contains(text(), 'Publish campaign')]/ancestor::material-button"))
                        )
                        publish_btn.click()
                        time.sleep(10)

                        # Check xem con o trang Review khong (co loi)
                        still_on_review = False
                        try:
                            driver.find_element(By.XPATH,
                                "//span[contains(text(), 'Publish campaign')]")
                            # Van con nut Publish = van o trang Review = co loi
                            still_on_review = True
                        except Exception:
                            still_on_review = False

                        if not still_on_review:
                            print(f"[OK] Publish thanh cong TK {account_id}")
                            break

                        # Co loi, tim section bao do de click vao sua
                        print(f"[!] Publish that bai, dang tim loi...")
                        error_sections = driver.find_elements(By.XPATH,
                            "//div[contains(@class, 'section-entry-wrap')]//material-icon[contains(@class, 'error')] | "
                            "//div[contains(@class, 'section-entry-wrap')][.//div[contains(@class, 'error')]]")

                        if error_sections:
                            for err_sec in error_sections:
                                try:
                                    if err_sec.is_displayed():
                                        print(f"[*] Tim thay section loi, click vao sua...")
                                        err_sec.click()
                                        time.sleep(5)
                                        # Quay lai Review
                                        for _ in range(5):
                                            try:
                                                next_btn_retry = driver.find_element(By.CSS_SELECTOR,
                                                    "material-button.button-next")
                                                next_btn_retry.click()
                                                time.sleep(3)
                                            except Exception:
                                                break
                                        break
                                except Exception:
                                    continue
                        else:
                            print(f"[!] Khong tim thay section loi cu the, thu lai...")
                            time.sleep(3)
                    else:
                        print(f"[!] Khong the publish TK {account_id} sau 3 lan thu, chuyen TK tiep")
                        continue

                    done += 1
                    print(f"[OK] === Hoan thanh TK {account_id} ({done}/{len(accounts)}) ===")

                except Exception as e:
                    print(f"[!] Loi TK {account_id}: {e}")
                    traceback.print_exc()
                    continue

    except KeyboardInterrupt:
        print("\n[!] Dung boi nguoi dung.")
    except Exception as e:
        print(f"[!] Loi: {e}")
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if current_genlogin:
            try:
                stop_profile(current_genlogin)
            except Exception:
                pass

    print(f"\n{'=' * 60}")
    print(f"   HOAN THANH: {done}/{len(accounts)} TK da xu ly")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Len camp tren TK Google Ads co san")
    parser.add_argument("limit", type=int, help="So luong TK Ads can chay")
    parser.add_argument("--project", required=True, help="Project ID tu DB")
    args = parser.parse_args()
    run(args.limit, args.project)
