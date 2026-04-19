#!/usr/bin/env python3
"""
continue_camp.py — Tiep tuc lam camp tu mot buoc cu the tren browser DA mo san.

Khac voi camp_runner.py:
- Chi chay 1 TK (khong da luong).
- Khong navigate vao Ads URL (assume browser dang o trang camp).
- Truyen --start-step de bo qua nhung buoc da xong.

Usage:
    python -X utf8 continue_camp.py --config '{"accounts":[{...}],...}' --start-step bidding
"""

import sys
import json
import argparse
import time
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests

from genlogin_api import (
    start_profile,
    get_debugger_address,
    connect_selenium,
    get_browser_version,
    resolve_profile_id,
)
from camp_google_ads_v3 import CampaignCreator
from status_tracker import StatusTracker


def _map_bidding(bidding_vn):
    mapping = {
        "Tối đa lượt nhấn chuột": "maximize_clicks",
        "Tối đa lượt chuyển đổi": "maximize_conversions",
        "CPC thủ công": "manual_cpc",
        "CPA mục tiêu": "target_cpa",
        "ROAS mục tiêu": "target_roas",
    }
    return mapping.get(bidding_vn, "maximize_clicks")


def log(msg, level="info"):
    prefix = {"info": "[INFO]", "error": "[ERROR]", "success": "[OK]", "warn": "[WARN]"}.get(level, "[INFO]")
    print(f"{prefix} {msg}", flush=True)


def get_or_start_profile(genlogin_id, profile_name=""):
    """Tra debugger_addr + browser_ver. Reuse port neu profile da chay."""
    resolved = resolve_profile_id(genlogin_id)
    if not resolved:
        raise Exception(f"Khong resolve duoc GenLogin profile: {genlogin_id}")

    debugger_addr = None
    browser_ver = None
    try:
        running_res = requests.get("http://localhost:55550/backend/profiles/running", timeout=5)
        for rp in running_res.json().get("data", []):
            if str(rp.get("id")) == str(resolved):
                port = rp.get("port")
                if port:
                    debugger_addr = f"127.0.0.1:{port}"
                    browser_ver = rp.get("browser_version")
                    log(f"[{profile_name}] Profile da mo san, dung port {port}")
                break
    except Exception:
        pass

    if not debugger_addr:
        log(f"[{profile_name}] Profile chua mo, dang start GenLogin {resolved}...")
        start_result = start_profile(resolved)
        debugger_addr = get_debugger_address(start_result)
        browser_ver = get_browser_version(start_result)

    if not debugger_addr:
        raise Exception(f"Khong lay duoc debugger address cho profile {resolved}")
    return debugger_addr, browser_ver


def run(config, start_step):
    accounts = config.get("accounts", [])
    if not accounts:
        log("Config khong co accounts!", "error")
        return

    acc = accounts[0]
    account_id = acc.get("accountId", "?")
    profile_name = acc.get("profileName", "?")
    genlogin_id = acc.get("genloginId")
    gmail_email = acc.get("gmail") or acc.get("gmailEmail") or ""
    profile_id = acc.get("profileId", "")

    log(f"=== TIEP TUC CAMP ===")
    log(f"PROFILE: {profile_name}")
    log(f"TK_ADS: {account_id}")
    log(f"START_STEP: {start_step or '(auto-detect)'}")

    if not genlogin_id:
        log(f"Profile '{profile_name}' khong co GenLogin ID!", "error")
        return

    try:
        debugger_addr, browser_ver = get_or_start_profile(genlogin_id, profile_name)
        log(f"[{profile_name}] Dang ket noi Selenium {debugger_addr}...")
        driver = connect_selenium(debugger_addr, browser_ver)
        log(f"[{profile_name}] Da ket noi Selenium!", "success")

        # Khong navigate — assume browser dang o trang camp
        log(f"[{profile_name}] URL hien tai: {driver.current_url[:120]}")
        log(f"[{profile_name}] Title hien tai: {driver.title[:80]}")

        # AUTO-DETECT start_step neu user khong truyen
        if not start_step:
            detected = CampaignCreator.detect_current_step(driver)
            if detected == "done":
                log(f"[{profile_name}] Trang da o campaigns list — camp cu da publish xong, khong can resume", "success")
                return
            log(f"[{profile_name}] [AUTO-DETECT] Phat hien dang o buoc: {detected}", "success")
            start_step = detected

        tracker = StatusTracker()
        account_data = {
            "accountId": account_id,
            "gmailEmail": gmail_email,
            "profileId": profile_id,
        }
        creator = CampaignCreator(driver, account_data, tracker)

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
            "target_locations": [l.strip() for l in (config.get("targetLocations") or "").split("|") if l.strip()],
            "exclude_locations": [l.strip() for l in (config.get("excludeLocations") or "").split("|") if l.strip()],
            "devices": [d.strip() for d in (config.get("devices") or "").split("|") if d.strip()],
            "age_ranges": [a.strip() for a in (config.get("ageRange") or "").split("|") if a.strip()],
            "gender": config.get("gender", ""),
        }

        log(f"[{profile_name}] Resume camp '{campaign_config['name']}' tu buoc '{start_step}'")
        try:
            success = creator.run_campaign_flow(
                campaign_config,
                skip_navigate=True,
                camp_index=1,
                start_step=start_step,
            )
            if success:
                log(f"[{profile_name}] Camp '{campaign_config['name']}' DA HOAN THANH!", "success")
            else:
                log(f"[{profile_name}] Camp '{campaign_config['name']}' THAT BAI", "error")
        except Exception as e:
            log(f"[{profile_name}] Loi khi resume camp: {e}", "error")
            traceback.print_exc()

    except Exception as e:
        log(f"[{profile_name}] Loi: {e}", "error")
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="JSON config (cung format voi camp_runner)")
    parser.add_argument("--start-step", required=False, default=None,
                        help="Buoc bat dau (bo trong de auto-detect): navigate|create|setup|bidding|settings|locations|languages|next_skip|keywords_ads|budget|publish")
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
    except json.JSONDecodeError as e:
        log(f"Loi parse config JSON: {e}", "error")
        sys.exit(1)

    run(config, args.start_step)


if __name__ == "__main__":
    main()
