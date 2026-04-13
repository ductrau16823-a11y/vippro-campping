#!/usr/bin/env python3
"""
=== VIPPRO CAMPPING ===
Main orchestrator: Tu dong tao campaign Google Ads cho nhieu TK cung luc.

Flow:
  1. Lay danh sach TK Ads tu DB (dashboard API)
  2. Moi TK -> mo GenLogin profile -> login Google -> vao Ads account
  3. Tao campaign -> ad group -> keywords -> ads -> set budget -> publish
  4. Track status realtime -> status.json
"""

import sys
import time
import traceback

# Fix encoding cho Windows console
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
    resolve_profile_id,
)
from api_helpers import (
    fetch_ads_accounts,
    fetch_campaign_data,
    fetch_gmail_profiles,
    upsert_campaign,
)
from status_tracker import StatusTracker
from camp_navigation_mixin import NavigationMixin
from camp_create_campaign_mixin import CreateCampaignMixin
from camp_adgroup_mixin import AdGroupMixin
from camp_ads_mixin import AdsMixin
from camp_budget_mixin import BudgetMixin
from camp_recovery_mixin import RecoveryMixin
from camp_edit_mixin import EditCampaignMixin


class CampaignCreator(
    NavigationMixin,
    CreateCampaignMixin,
    AdGroupMixin,
    AdsMixin,
    BudgetMixin,
    RecoveryMixin,
    EditCampaignMixin,
):
    """Tao campaign tu dong cho 1 TK Ads."""

    def __init__(self, driver, account_data, tracker):
        """
        Args:
            driver: Selenium WebDriver (da ket noi GenLogin)
            account_data: dict {accountId, gmailEmail, profileId, ...}
            tracker: StatusTracker instance
        """
        self.driver = driver
        self.account_data = account_data
        self.tracker = tracker
        self.customer_id = account_data.get("accountId", "")
        self.gmail = account_data.get("gmailEmail", "")

    def run_campaign_flow(self, campaign_config):
        """Chay toan bo flow tao 1 campaign.

        Args:
            campaign_config: dict {
                'name': str,           # Ten campaign
                'goal': str,           # sales | leads | traffic | without_goal
                'type': str,           # search | display | performance_max
                'budget': int/str,     # Budget hang ngay
                'bidding': str,        # maximize_clicks | maximize_conversions
                'adgroup_name': str,   # Ten ad group
                'keywords': list,      # List keywords
                'final_url': str,      # URL trang dich
                'headlines': list,     # List headlines (3-15)
                'descriptions': list,  # List descriptions (2-4)
            }
        """
        name = campaign_config.get("name", "Campaign 1")
        self.tracker.log(f"=== Bat dau tao campaign: {name} ===")

        # 1. Navigate vao TK Ads
        self.navigate_to_ads_account(self.customer_id)

        # 2. Bat dau tao campaign moi
        self.start_new_campaign(self.customer_id)

        # 3. Chon goal
        goal = campaign_config.get("goal", "traffic")
        self.select_campaign_goal(goal)

        # 4. Chon campaign type
        camp_type = campaign_config.get("type", "search")
        self.select_campaign_type(camp_type)

        # 5. Set budget + bidding
        budget = campaign_config.get("budget", 50000)
        self.fill_budget(budget)

        bidding = campaign_config.get("bidding", "maximize_clicks")
        self.select_bidding_strategy(bidding)
        self.click_next_budget()

        # 6. Tao ad group + keywords
        adgroup_name = campaign_config.get("adgroup_name", "Ad Group 1")
        self.fill_adgroup_name(adgroup_name)

        keywords = campaign_config.get("keywords", [])
        if keywords:
            self.fill_keywords(keywords)
        self.click_next_adgroup()

        # 7. Tao ads
        final_url = campaign_config.get("final_url", "")
        if final_url:
            self.fill_final_url(final_url)

        headlines = campaign_config.get("headlines", [])
        if headlines:
            self.fill_headlines(headlines)

        descriptions = campaign_config.get("descriptions", [])
        if descriptions:
            self.fill_descriptions(descriptions)
        self.click_next_ads()

        # 8. Review & Publish
        self.wait_loading_done()
        error = self.check_and_handle_error()
        if error:
            self.tracker.log(f"Loi truoc khi publish: {error}", "error")
            return False

        self.publish_campaign()
        time.sleep(3)

        # 9. Check ket qua
        error = self.check_and_handle_error()
        if error:
            self.tracker.log(f"Loi sau khi publish: {error}", "error")
            return False

        # 10. Chinh sua demographics (age, gender) neu DB co config
        self.edit_campaign_demographics(campaign_config)

        # 11. Luu vao DB
        upsert_campaign(self.customer_id, name, status="published")
        self.tracker.log(f"Campaign '{name}' da duoc publish thanh cong!", "success")
        return True


def main():
    """Entry point: Chay tu dong tao campaign cho tat ca TK Ads."""
    print("=" * 60)
    print("   VIPPRO CAMPPING - Auto Campaign Creator")
    print("=" * 60)

    tracker = StatusTracker()

    # 1. Lay danh sach TK Ads tu DB
    tracker.log("Dang lay danh sach TK Ads tu DB...")
    accounts = fetch_ads_accounts(status="verified")

    if not accounts:
        tracker.log("Khong co TK Ads nao (status=verified) de camp!", "error")
        tracker.finish("error")
        return

    tracker.data["total_accounts"] = len(accounts)
    tracker.log(f"Tim thay {len(accounts)} TK Ads can camp")

    # 2. Lay danh sach Gmail profiles (de biet profileId cua moi Gmail)
    profiles = fetch_gmail_profiles()
    profile_map = {p.get("email"): p for p in profiles}

    # 3. Loop qua tung TK
    for idx, account in enumerate(accounts, 1):
        account_id = account.get("accountId", "?")
        gmail = account.get("gmailEmail", "?")
        profile_id = None

        tracker.log(f"\n{'='*40}")
        tracker.log(f"[{idx}/{len(accounts)}] TK: {account_id} | Gmail: {gmail}")

        # Tim profileId tu Gmail
        profile_info = profile_map.get(gmail)
        if profile_info:
            profile_id = profile_info.get("genloginProfileId") or profile_info.get("profileId")

        if not profile_id:
            tracker.log(f"Khong tim thay GenLogin profile cho {gmail}, skip!", "error")
            tracker.add_account_result(account_id, gmail, 0, "error", "No GenLogin profile")
            continue

        # Resolve profile ID (co the la ten hoac so)
        resolved_id = resolve_profile_id(profile_id)
        if not resolved_id:
            tracker.log(f"Khong resolve duoc profile ID: {profile_id}, skip!", "error")
            tracker.add_account_result(account_id, gmail, 0, "error", "Cannot resolve profile")
            continue

        driver = None
        try:
            # Start GenLogin profile
            tracker.set_current(account=account_id, step="Start GenLogin profile")
            start_result = start_profile(resolved_id)
            debugger_addr = get_debugger_address(start_result)
            browser_ver = get_browser_version(start_result)

            if not debugger_addr:
                raise Exception(f"Khong lay duoc debugger address tu profile {resolved_id}")

            # Connect Selenium
            tracker.set_current(step="Ket noi Selenium")
            driver = connect_selenium(debugger_addr, browser_ver)
            tracker.log("Da ket noi Selenium thanh cong")

            # Tao CampaignCreator
            creator = CampaignCreator(driver, account, tracker)

            # Lay campaign data tu DB
            campaign_configs = fetch_campaign_data(account_id)

            if not campaign_configs:
                # Mac dinh: tao 1 campaign test
                tracker.log("Khong co campaign data tu DB, dung config mac dinh", "warn")
                campaign_configs = [{
                    "name": f"Camp_{account_id}",
                    "goal": "traffic",
                    "type": "search",
                    "budget": 50000,
                    "bidding": "maximize_clicks",
                    "adgroup_name": "Ad Group 1",
                    "keywords": ["tu khoa 1", "tu khoa 2"],
                    "final_url": "https://example.com",
                    "headlines": ["Tieu de 1", "Tieu de 2", "Tieu de 3"],
                    "descriptions": ["Mo ta 1", "Mo ta 2"],
                }]

            campaigns_created = 0
            for config in campaign_configs:
                try:
                    success = creator.run_campaign_flow(config)
                    if success:
                        campaigns_created += 1
                except Exception as e:
                    tracker.log(f"Loi tao campaign '{config.get('name')}': {e}", "error")
                    traceback.print_exc()

            tracker.add_account_result(
                account_id, gmail, campaigns_created,
                "success" if campaigns_created > 0 else "error",
            )

        except Exception as e:
            tracker.log(f"Loi xu ly TK {account_id}: {e}", "error")
            traceback.print_exc()
            tracker.add_account_result(account_id, gmail, 0, "error", str(e))

        finally:
            # Tat GenLogin profile
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            try:
                stop_profile(resolved_id)
            except Exception:
                pass

    # Hoan thanh
    tracker.finish()
    total = tracker.data["total_campaigns_created"]
    processed = tracker.data["processed_accounts"]
    print(f"\n{'='*60}")
    print(f"   HOAN THANH: {total} campaigns tao cho {processed} TK")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
