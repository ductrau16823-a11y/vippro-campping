#!/usr/bin/env python3
"""
camp_runner.py — Nhận config + danh sách TK từ dashboard, mở GenLogin đa luồng.
Usage: python -X utf8 camp_runner.py --config '{"accounts":[...],...}'
"""

import sys
import os
import json
import argparse
import time
import traceback
import threading
import atexit
import signal

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# === ATEXIT + SIGNAL HANDLER: log ly do process thoat ===
_last_exit_info = {"reason": "normal_exit", "exc": None}

def _atexit_log():
    try:
        print(f"[ATEXIT] Process thoat: reason={_last_exit_info['reason']} exc={_last_exit_info['exc']}", flush=True)
        # Flush status.json cuoi cung
        try:
            from status_tracker import StatusTracker as _ST
            _t = _ST()
            _t.log(f"[ATEXIT] Process thoat: {_last_exit_info['reason']} | {_last_exit_info['exc']}", "error" if _last_exit_info['exc'] else "info")
        except Exception:
            pass
    except Exception:
        pass

atexit.register(_atexit_log)

def _signal_handler(sig, frame):
    _last_exit_info["reason"] = f"signal_{sig}"
    try:
        print(f"[SIGNAL] Nhan signal {sig} — thoat", flush=True)
    except Exception:
        pass
    sys.exit(1)

try:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _signal_handler)
except Exception:
    pass

# Hook exception khong bat duoc (unhandled exception o main thread)
def _excepthook(exc_type, exc, tb):
    _last_exit_info["reason"] = "unhandled_exception"
    _last_exit_info["exc"] = f"{exc_type.__name__}: {exc}"
    try:
        traceback.print_exception(exc_type, exc, tb)
    except Exception:
        pass

sys.excepthook = _excepthook

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import requests
from genlogin_api import start_profile, get_debugger_address, connect_selenium, get_browser_version, resolve_profile_id
from db_helpers import _connect
from camp_google_ads_v3 import CampaignCreator
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


def check_account_status(driver, profile_name, account_id, account_db_id=None):
    """Check trang thai TK Ads — xem co suspended hay OK.
    Neu gap trang billing/setup thi reload lai thay vi skip.

    Return: "ok" | "suspended"
    """
    try:
        page_source = driver.page_source.lower()
        current_url = driver.current_url.lower()

        # Neu da vao duoc trang Campaigns -> coi nhu OK, khong reload
        # Banner "Verify your payment information" tren dau trang KHONG phai ly do reload
        if "/aw/campaigns" in current_url:
            # Van check suspended
            suspended_indicators = [
                "your account is suspended",
                "account suspended",
                "this account has been suspended",
                "account is currently suspended",
            ]
            for indicator in suspended_indicators:
                if indicator in page_source:
                    log(f"[{profile_name}] TK {account_id} BI SUSPENDED — skip!", "error")
                    if account_db_id:
                        update_account_status(account_db_id, "suspended", "Account is suspended")
                    return "suspended"
            return "ok"

        # TK bi suspended — KHONG len camp, update DB de sau khang
        suspended_indicators = [
            "your account is suspended",
            "account suspended",
            "this account has been suspended",
            "account is currently suspended",
        ]
        for indicator in suspended_indicators:
            if indicator in page_source:
                log(f"[{profile_name}] TK {account_id} BI SUSPENDED — skip!", "error")
                if account_db_id:
                    update_account_status(account_db_id, "suspended", "Account is suspended")
                return "suspended"

        # TK gap trang billing/setup — reload lai trang Campaigns
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
                log(f"[{profile_name}] Gap trang '{indicator}' — reload lai...", "warn")
                # Navigate lai ve Campaigns
                cid = account_id.replace("-", "")
                driver.get(f"https://ads.google.com/aw/campaigns?__e={cid}")
                time.sleep(10)
                # Check lai — neu van bi thi thu 1 lan nua
                new_url = driver.current_url.lower()
                new_source = driver.page_source[:3000].lower()
                still_setup = any(ind in new_source or ind in new_url for ind in setup_indicators)
                if still_setup:
                    log(f"[{profile_name}] Van gap setup sau reload — thu lan nua...", "warn")
                    driver.get(f"https://ads.google.com/aw/campaigns?__e={cid}")
                    time.sleep(10)
                log(f"[{profile_name}] Da reload — Title: {driver.title}")
                return "ok"

        return "ok"
    except Exception:
        return "ok"

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
        items = WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "material-list-item")
        )

        for item in items:
            text = item.text
            if account_id in text:
                if "Setup in progress" in text or "setup" in text.lower():
                    log(f"[{profile_name}] TK {account_id} co 'Setup in progress' — SKIP", "warn")
                    return False
                item.click()
                log(f"[{profile_name}] Da click chon TK {account_id}, cho trang load...", "success")
                time.sleep(15)
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
    # Retry toi 3 lan: sau khi chon TK, Google co the quay lai Account Chooser (chon Gmail) lan nua
    for _ in range(3):
        if "/selectaccount" in driver.current_url:
            ok = handle_ads_account_selector(driver, account_id, profile_name)
            if not ok:
                return False
            time.sleep(5)
            # Sau khi chon TK, check xem co quay ve Account Chooser / login khong
            if handle_account_chooser(driver, gmail_email, profile_name):
                time.sleep(3)
                handle_gmail_login(driver, gmail_email, profile_id, profile_name)
                time.sleep(3)
                continue  # loop lai de chon TK lan nua
            return True
        # Neu khong phai trang selectaccount -> da vao duoc TK
        if "ads.google.com" in driver.current_url and "/selectaccount" not in driver.current_url:
            return True
        time.sleep(3)

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
        # Check profile da running chua — neu roi thi lay port luon
        debugger_addr = None
        browser_ver = None
        try:
            running_res = requests.get(f"http://localhost:55550/backend/profiles/running", timeout=5)
            for rp in running_res.json().get("data", []):
                if str(rp.get("id")) == str(resolved_id):
                    port = rp.get("port")
                    if port:
                        debugger_addr = f"127.0.0.1:{port}"
                        browser_ver = rp.get("browser_version")
                        log(f"[{profile_name}] Profile da mo san, port {port}")
                    break
        except Exception:
            pass

        if not debugger_addr:
            start_result = start_profile(resolved_id)
            debugger_addr = get_debugger_address(start_result)
            browser_ver = get_browser_version(start_result)

        if not debugger_addr:
            raise Exception(f"Khong lay duoc debugger address tu profile {resolved_id}")

        log(f"[{profile_name}] Dang ket noi Selenium...")
        driver = connect_selenium(debugger_addr, browser_ver)
        log(f"[{profile_name}] Da ket noi Selenium!", "success")

        # Navigate vao TK Ads
        ads_url = f"https://ads.google.com/aw/campaigns?__e={account_id.replace('-', '')}"
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

        # Check TK: suspended + needs_setup deu skip, khong len camp
        account_db_id = acc.get("dbId")
        tk_status = check_account_status(driver, profile_name, account_id, account_db_id)
        if tk_status != "ok":
            log(f"[{profile_name}] TK {account_id} status={tk_status} — SKIP!", "warn")
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
            "budget": str(config.get("budget") or "5"),
            "bidding": _map_bidding(config.get("bidding", "")),
            "cpc": str(config.get("cpc") or ""),
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

        # Dem so camp da co tren TK nay de danh so (viltrox 1, viltrox 2...)
        camp_index = 1
        try:
            from api_helpers import fetch_ads_account_by_id
            acc_detail = fetch_ads_account_by_id(account_id)
            if acc_detail:
                existing_count = acc_detail.get("_count", {}).get("campaigns", 0)
                camp_index = existing_count + 1
        except Exception:
            pass

        log(f"[{profile_name}] Dang tao campaign: {campaign_config['name']} (#{camp_index})")
        try:
            ok = creator.run_campaign_flow(
                campaign_config,
                skip_navigate=True,
                camp_index=camp_index,
                start_step=None,
            )
            if ok:
                log(f"[{profile_name}] Campaign '{campaign_config['name']}' DA PUBLISH THANH CONG!", "success")
            else:
                log(f"[{profile_name}] Campaign '{campaign_config['name']}' THAT BAI", "error")
        except BaseException as e:
            # BaseException -> bat ca SystemExit/KeyboardInterrupt/GeneratorExit de lo nguyen nhan chet ngam
            tb_str = traceback.format_exc()
            log(f"[{profile_name}] Campaign '{campaign_config['name']}' LOI: {type(e).__name__}: {e}", "error")
            for ln in tb_str.splitlines():
                log(f"[TRACE] {ln}", "error")
            try:
                tracker.log(f"[CRITICAL] run_campaign_flow raised {type(e).__name__}: {e}", "error")
                for ln in tb_str.splitlines():
                    tracker.log(f"[TRACE] {ln}", "error")
            except Exception:
                pass
            try:
                sys.stdout.flush()
            except Exception:
                pass

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
