#!/usr/bin/env python3
"""
camp_runner.py — Nhận config + danh sách TK từ dashboard, mở GenLogin đa luồng.
Usage: python -X utf8 camp_runner.py --config '{"accounts":[...],...}'
"""

import sys
import json
import argparse
import time
import traceback
import threading

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import requests
from genlogin_api import start_profile, stop_profile, get_debugger_address, connect_selenium, get_browser_version, resolve_profile_id
from db_helpers import _connect
from camp_google_ads import CampaignCreator
from status_tracker import StatusTracker

DASHBOARD_API = "http://localhost:3000/api"


def _map_bidding(bidding_vn):
    """Map ten chien luoc gia thau tieng Viet -> value cho CampaignCreator."""
    mapping = {
        "Tối đa lượt nhấn chuột": "maximize_clicks",
        "Tối đa lượt chuyển đổi": "maximize_conversions",
        "CPC thủ công": "manual_cpc",
        "CPA mục tiêu": "target_cpa",
        "ROAS mục tiêu": "target_roas",
    }
    return mapping.get(bidding_vn, "maximize_clicks")


def update_account_status(account_db_id, new_status, notes=None):
    """Update status TK Ads tren DB qua API."""
    try:
        payload = {"status": new_status}
        if notes:
            payload["notes"] = notes
        requests.put(f"{DASHBOARD_API}/ads-accounts/{account_db_id}", json=payload, timeout=10)
        log(f"DB updated: {account_db_id} -> {new_status}")
    except Exception as e:
        log(f"Loi update DB: {e}", "error")


def check_needs_setup(driver, profile_name):
    """Check xem TK Ads con dang o trang setup hay da vao duoc dashboard.

    Return: True neu can setup (chua hoan thanh), False neu OK.
    """
    try:
        page_source = driver.page_source.lower()
        current_url = driver.current_url.lower()

        # Cac dau hieu TK chua setup xong
        setup_indicators = [
            "complete your account setup",
            "finish setting up",
            "complete setup",
            "billing setup",
            "add payment method",
            "enter your billing",
            "set up billing",
            "/aw/signup",
            "/aw/billing/setup",
            "verify your business",
        ]

        for indicator in setup_indicators:
            if indicator in page_source or indicator in current_url:
                log(f"[{profile_name}] TK chua setup xong: tim thay '{indicator}'", "warn")
                return True

        return False
    except Exception:
        return False

# Thread-safe log
_log_lock = threading.Lock()

def log(msg, level="info"):
    prefix = {"info": "[INFO]", "error": "[ERROR]", "success": "[OK]", "warn": "[WARN]"}.get(level, "[INFO]")
    with _log_lock:
        print(f"{prefix} {msg}", flush=True)


# Track progress
_progress_lock = threading.Lock()
_success_count = 0
_total_count = 0


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


def get_gmail_password(profile_id):
    """Lay password Gmail tu DB thong qua Profile."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT g.password
            FROM Profile p
            JOIN Gmail g ON p.gmailId = g.id
            WHERE p.id = ?
        """, (profile_id,))
        row = cur.fetchone()
        return row["password"] if row and row["password"] else None
    finally:
        conn.close()


def generate_totp(secret):
    """Generate ma TOTP tu secret key."""
    import pyotp
    return pyotp.TOTP(secret).now()


def handle_account_chooser(driver, gmail_email, profile_name):
    """Xu ly trang 'Choose an account' (Google login) — click vao dung gmail.

    Return: True neu da click, False neu khong gap trang nay.
    """
    try:
        heading = driver.find_element(By.CSS_SELECTOR, "h1#headingText span")
        if "Choose an account" not in heading.text and "Chọn tài khoản" not in heading.text:
            return False
    except Exception:
        return False

    log(f"[{profile_name}] Gap trang Account Chooser, dang chon gmail...")

    if gmail_email:
        # Google hien email lowercase tren trang
        email_lower = gmail_email.lower()
        try:
            account_el = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    f'div[data-identifier="{email_lower}"]'
                ))
            )
            account_el.click()
            log(f"[{profile_name}] Da click chon {email_lower}", "success")
            time.sleep(5)
            return True
        except Exception:
            log(f"[{profile_name}] Khong tim thay gmail {email_lower} tren trang!", "error")

    log(f"[{profile_name}] Khong chon duoc account, skip!", "error")
    return False


def handle_ads_account_selector(driver, account_id, profile_name):
    """Xu ly trang Select Account cua Google Ads — chon dung TK theo ID.
    Skip TK co 'Setup in progress'.

    Return: True neu click duoc TK, False neu khong.
    """
    try:
        # Check co phai trang selectaccount khong
        if "/selectaccount" not in driver.current_url and "material-list-item" not in driver.page_source:
            return False
    except Exception:
        return False

    log(f"[{profile_name}] Gap trang chon TK Ads, dang tim {account_id}...")

    try:
        items = WebDriverWait(driver, 10).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "material-list-item")
        )

        for item in items:
            text = item.text
            if account_id in text:
                if "Setup in progress" in text or "setup" in text.lower():
                    log(f"[{profile_name}] TK {account_id} co 'Setup in progress' — SKIP", "warn")
                    return False
                item.click()
                log(f"[{profile_name}] Da click chon TK {account_id}", "success")
                time.sleep(8)
                return True

        log(f"[{profile_name}] Khong tim thay TK {account_id} tren trang!", "error")
        return False
    except Exception as e:
        log(f"[{profile_name}] Loi chon TK Ads: {e}", "error")
        return False


def handle_gmail_login(driver, gmail_email, profile_id, profile_name):
    """Xu ly login lai Gmail khi bi hoi nhap email/password.

    Return: True neu login thanh cong, False neu khong.
    """
    # Check trang nhap email (identifier)
    try:
        email_input = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']#identifierId"))
        )
    except Exception:
        return False

    log(f"[{profile_name}] Gap trang login, dang nhap email...")

    # Nhap email
    email_input.clear()
    email_input.send_keys(gmail_email)
    time.sleep(0.5)

    # Click Next
    try:
        next_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#identifierNext button"))
        )
        next_btn.click()
        time.sleep(4)
    except Exception as e:
        log(f"[{profile_name}] Khong click duoc Next sau email: {e}", "error")
        return False

    # Nhap password
    password = get_gmail_password(profile_id)
    if not password:
        log(f"[{profile_name}] Khong co password trong DB!", "error")
        return False

    try:
        pw_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'][name='Passwd']"))
        )
        pw_input.clear()
        pw_input.send_keys(password)
        time.sleep(0.5)

        pw_next = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#passwordNext button"))
        )
        pw_next.click()
        log(f"[{profile_name}] Da nhap password, dang cho...", "success")
        time.sleep(5)
    except Exception as e:
        log(f"[{profile_name}] Loi nhap password: {e}", "error")
        return False

    # Check 2FA
    try:
        totp_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#totpPin"))
        )
        log(f"[{profile_name}] Gap trang 2FA, dang nhap ma...")
        secret = get_2fa_key(profile_id)
        if not secret:
            log(f"[{profile_name}] Khong co twoFactorKey trong DB!", "error")
            return False

        code = generate_totp(secret)
        totp_input.click()
        time.sleep(0.3)
        totp_input.send_keys(code)
        time.sleep(1)

        totp_next = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#totpNext button"))
        )
        totp_next.click()
        log(f"[{profile_name}] Da nhap 2FA: {code}", "success")
        time.sleep(5)
    except Exception:
        # Khong co 2FA -> OK, tiep tuc
        pass

    return True


def handle_post_navigate(driver, gmail_email, profile_id, profile_name, account_id):
    """Sau khi navigate vao Ads URL, xu ly cac truong hop:
    1. Google Account Chooser -> click gmail
    2. Login lai -> nhap email/pw/2fa
    3. Google Ads Account Selector -> click dung TK Ads

    Return: True neu vao duoc TK thanh cong, False neu bi skip/loi.
    """
    # Buoc 1: Check Google Account Chooser (chon gmail)
    if handle_account_chooser(driver, gmail_email, profile_name):
        time.sleep(3)
        # Sau khi chon account, co the can login lai
        if handle_gmail_login(driver, gmail_email, profile_id, profile_name):
            time.sleep(3)
        # Sau login co the lai gap Account Chooser
        handle_account_chooser(driver, gmail_email, profile_name)
        time.sleep(3)

    # Buoc 1b: Check Login (neu khong gap Account Chooser)
    elif handle_gmail_login(driver, gmail_email, profile_id, profile_name):
        time.sleep(3)
        handle_account_chooser(driver, gmail_email, profile_name)
        time.sleep(3)

    # Buoc 2: Check Google Ads Account Selector (chon TK Ads cu the)
    if "/selectaccount" in driver.current_url:
        return handle_ads_account_selector(driver, account_id, profile_name)

    return True


def run_single_account(acc, config):
    """Chạy 1 TK trong 1 thread riêng."""
    global _success_count

    account_id = acc.get("accountId", "?")
    profile_name = acc.get("profileName", "?")
    genlogin_id = acc.get("genloginId")
    gmail_email = acc.get("gmail") or acc.get("gmailEmail") or ""
    profile_id = acc.get("profileId", "")

    log(f"PROFILE: {profile_name}")
    log(f"TK_ADS: {account_id}")

    if not genlogin_id:
        log(f"Khong co GenLogin ID cho profile '{profile_name}', skip!", "error")
        return

    resolved_id = resolve_profile_id(genlogin_id)
    if not resolved_id:
        log(f"Khong resolve duoc GenLogin profile: {genlogin_id}, skip!", "error")
        return

    try:
        log(f"[{profile_name}] Dang mo GenLogin profile {resolved_id}...")
        start_result = start_profile(resolved_id)
        debugger_addr = get_debugger_address(start_result)
        browser_ver = get_browser_version(start_result)

        if not debugger_addr:
            raise Exception(f"Khong lay duoc debugger address tu profile {resolved_id}")

        log(f"[{profile_name}] Dang ket noi Selenium...")
        driver = connect_selenium(debugger_addr, browser_ver)
        log(f"[{profile_name}] Da ket noi Selenium!", "success")

        # Navigate vao TK Ads
        ads_url = f"https://ads.google.com/aw/campaigns?ocid={account_id.replace('-', '')}"
        log(f"[{profile_name}] Dang vao: {ads_url}")
        driver.get(ads_url)
        time.sleep(5)

        # Xu ly Account Chooser / Login / Chon TK Ads
        ok = handle_post_navigate(driver, gmail_email, profile_id, profile_name, account_id)
        if not ok:
            log(f"[{profile_name}] Khong vao duoc TK {account_id}, skip!", "error")
            account_db_id = acc.get("dbId")
            if account_db_id:
                update_account_status(account_db_id, "needs_setup", "TK co Setup in progress hoac khong chon duoc")
            return
        time.sleep(3)

        # Check setup — TK chua setup xong thi SKIP, khong len camp
        if check_needs_setup(driver, profile_name):
            log(f"[{profile_name}] TK {account_id} chua setup xong — SKIP, khong len camp!", "warn")
            account_db_id = acc.get("dbId")
            if account_db_id:
                update_account_status(account_db_id, "needs_setup", "TK chua setup xong (billing/verify)")
            return

        log(f"[{profile_name}] TK {account_id} — bat dau len camp", "success")

        # === TAO CAMPAIGN TU CONFIG DU AN ===
        tracker = StatusTracker()
        account_data = {
            "accountId": account_id,
            "gmailEmail": gmail_email,
            "profileId": profile_id,
        }
        creator = CampaignCreator(driver, account_data, tracker)

        # Build campaign config tu project data
        campaign_config = {
            "name": config.get("name", "Campaign"),
            "goal": "traffic",
            "type": (config.get("campaignType") or "search").lower(),
            "budget": config.get("budget", "5"),
            "bidding": _map_bidding(config.get("bidding", "")),
            "adgroup_name": f"AG_{config.get('name', 'Group')}",
            "keywords": [k.strip() for k in (config.get("adsKey") or "").split("|") if k.strip()],
            "final_url": config.get("link1", ""),
            "headlines": [h.strip() for h in (config.get("headlines") or "").split("|") if h.strip()],
            "descriptions": [d.strip() for d in (config.get("descriptions") or "").split("|") if d.strip()],
            # Targeting
            "target_locations": [l.strip() for l in (config.get("targetLocations") or "").split("|") if l.strip()],
            "exclude_locations": [l.strip() for l in (config.get("excludeLocations") or "").split("|") if l.strip()],
            "devices": [d.strip() for d in (config.get("devices") or "").split("|") if d.strip()],
            "age_ranges": [a.strip() for a in (config.get("ageRange") or "").split("|") if a.strip()],
            "gender": config.get("gender", ""),
        }

        log(f"[{profile_name}] Dang tao campaign: {campaign_config['name']}")
        try:
            success = creator.run_campaign_flow(campaign_config, skip_navigate=True)
            if success:
                log(f"[{profile_name}] Campaign '{campaign_config['name']}' DA PUBLISH THANH CONG!", "success")
            else:
                log(f"[{profile_name}] Campaign '{campaign_config['name']}' THAT BAI", "error")
        except Exception as e:
            log(f"[{profile_name}] Loi tao campaign: {e}", "error")
            traceback.print_exc()

        with _progress_lock:
            _success_count += 1
            log(f"TIEN_DO: {_success_count}/{_total_count}")

    except Exception as e:
        log(f"[{profile_name}] Loi TK {account_id}: {e}", "error")
        traceback.print_exc()


def run(config):
    global _total_count, _success_count

    project_name = config.get("name", "?")
    accounts = config.get("accounts", [])
    _total_count = len(accounts)
    _success_count = 0

    log(f"=== Du an: {project_name} ===")
    log(f"So TK can chay: {_total_count}")
    log(f"Che do: DA LUONG ({_total_count} browser dong thoi)")

    if not accounts:
        log("Khong co TK nao duoc chon!", "error")
        return

    # Group accounts theo genloginId (nhiều TK cùng 1 profile -> chạy tuần tự trong profile đó)
    profile_groups = {}
    for acc in accounts:
        gid = acc.get("genloginId", "?")
        if gid not in profile_groups:
            profile_groups[gid] = []
        profile_groups[gid].append(acc)

    log(f"So profile can mo: {len(profile_groups)}")

    # Chạy mỗi profile group trong 1 thread
    threads = []
    for gid, accs in profile_groups.items():
        # Trong 1 profile, chạy tuần tự các TK (vì dùng chung 1 browser)
        def run_profile_group(accs_list=accs):
            for acc in accs_list:
                run_single_account(acc, config)
                if len(accs_list) > 1:
                    time.sleep(2)  # delay giữa các TK cùng profile

        t = threading.Thread(target=run_profile_group, daemon=True)
        threads.append(t)
        t.start()
        time.sleep(1)  # delay giữa các profile để GenLogin không bị quá tải

    # Đợi tất cả threads hoàn thành
    for t in threads:
        t.join(timeout=120)  # max 2 phút mỗi thread

    log(f"\n{'='*50}")
    log(f"HOAN THANH: {_success_count}/{_total_count} TK da mo thanh cong", "success")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
    except json.JSONDecodeError as e:
        log(f"Loi parse config JSON: {e}", "error")
        sys.exit(1)

    run(config)


if __name__ == "__main__":
    main()
