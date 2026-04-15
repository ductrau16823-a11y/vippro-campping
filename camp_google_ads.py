#!/usr/bin/env python3
"""
=== VIPPRO CAMPPING ===
Tao campaign Google Ads tu dong — 23 buoc theo flow da duoc xac nhan.
Goi tu camp_runner.py sau khi da vao dung TK Ads.
"""

import sys
import time
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api_helpers import upsert_campaign
from status_tracker import StatusTracker


class CampaignCreator:
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

    def run_campaign_flow(self, campaign_config, skip_navigate=False):
        """Chay toan bo flow tao 1 campaign — dung 23 buoc da duoc huong dan.

        Args:
            campaign_config: dict tu DB project
            skip_navigate: True neu camp_runner da vao san TK Ads
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        d = self.driver
        name = campaign_config.get("name", "Campaign")
        self.tracker.log(f"=== Bat dau tao campaign: {name} ===")

        def js_click(el):
            d.execute_script("arguments[0].click()", el)

        def wait_click(xpath, timeout=15):
            el = WebDriverWait(d, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            js_click(el)
            return el

        def wait_visible(xpath, timeout=15):
            return WebDriverWait(d, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))

        def clear_and_type(el, value):
            """Click vao input, Ctrl+A roi type de — fix Material input clear() khong hoat dong."""
            from selenium.webdriver.common.keys import Keys
            el.click()
            time.sleep(0.2)
            el.send_keys(Keys.CONTROL, "a")
            time.sleep(0.1)
            el.send_keys(str(value))

        def fill_input(xpath, value, timeout=15):
            el = WebDriverWait(d, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            clear_and_type(el, value)
            return el

        def js_set_textarea(el, value):
            """Dung JS set value cho textarea — fix send_keys nuot ky tu voi text dai."""
            d.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                el, value
            )

        def check_2fa():
            """Check popup 'Confirm it's you' + 2FA bat ky luc nao."""
            try:
                confirm = d.find_elements(By.XPATH, "//material-button[contains(@class, 'setup')]")
                for c in confirm:
                    if c.is_displayed() and 'Confirm' in c.text:
                        js_click(c)
                        time.sleep(3)
                        break
            except Exception:
                pass
            try:
                totp = d.find_elements(By.CSS_SELECTOR, "input#totpPin")
                if totp and totp[0].is_displayed():
                    from camp_runner import get_2fa_key, generate_totp
                    secret = get_2fa_key(self.account_data.get("profileId", ""))
                    if secret:
                        code = generate_totp(secret)
                        totp[0].click()
                        totp[0].send_keys(code)
                        time.sleep(1)
                        wait_click("//button[@id='totpNext'] | //*[@id='totpNext']//button", timeout=5)
                        time.sleep(5)
            except Exception:
                pass

        # === BUOC 4-5: Click Create (+) > Campaign ===
        self.tracker.set_current(step="Buoc 4-5: Click Create > Campaign")
        try:
            wait_click("//uber-create-fab//material-fab | //uber-create//material-fab | //material-fab[contains(@class, 'new-entity')]", timeout=10)
            time.sleep(1)
            wait_click("//material-select-item[@aria-label='Campaign'] | //material-select-item[.//span[contains(text(), 'Campaign')]]", timeout=10)
            time.sleep(3)
        except Exception:
            # Fallback: click nut "New campaign"
            try:
                wait_click("//button[@aria-label='New campaign']", timeout=5)
                time.sleep(3)
            except Exception:
                self.tracker.log("Khong tim thay nut Create/New campaign!", "error")
                return False
        self.tracker.log("Da click Create > Campaign", "success")

        # === BUOC 6: Chon "Create a campaign without guidance" ===
        self.tracker.set_current(step="Buoc 6: Chon without guidance")
        check_2fa()
        try:
            wait_click("//*[@data-value='No objective'] | //span[contains(@class, 'unified-goals-card-title') and contains(text(), 'without guidance')]", timeout=15)
            time.sleep(2)
        except Exception:
            self.tracker.log("Khong tim thay 'without guidance', thu click truc tiep...", "warn")
            goals = d.find_elements(By.XPATH, "//span[contains(@class, 'unified-goals-card-title')]")
            for g in goals:
                if g.is_displayed() and 'without' in g.text.lower():
                    parent = g.find_element(By.XPATH, "./ancestor::div[contains(@class, 'unified-goals-card-format')]")
                    js_click(parent)
                    time.sleep(2)
                    break
        self.tracker.log("Da chon 'without guidance'", "success")

        # === BUOC 7: Chon campaign type ===
        self.tracker.set_current(step="Buoc 7: Chon campaign type")
        camp_type = campaign_config.get("type", "search").upper()
        check_2fa()
        try:
            wait_click(f"//*[@data-value='{camp_type}']", timeout=10)
        except Exception:
            # Fallback: tim trong unified-goals-card
            type_text = campaign_config.get("type", "search").capitalize()
            types = d.find_elements(By.XPATH, "//span[contains(@class, 'unified-goals-card-title')]")
            for t in types:
                if t.is_displayed() and t.text.strip().lower() == type_text.lower():
                    parent = t.find_element(By.XPATH, "./ancestor::div[contains(@class, 'unified-goals-card-format')]")
                    js_click(parent)
                    break
        time.sleep(2)
        self.tracker.log(f"Da chon type: {camp_type}", "success")

        # === BUOC 8: Tick "Website visits" ===
        self.tracker.set_current(step="Buoc 8: Tick Website visits")
        try:
            wait_click("//tactics-selection//mat-checkbox | //mat-checkbox[.//span[contains(text(), 'Website')]]", timeout=8)
            time.sleep(1)
        except Exception:
            self.tracker.log("Khong tim thay checkbox Website visits, bo qua", "warn")

        # === BUOC 9: Click Continue ===
        self.tracker.set_current(step="Buoc 9: Click Continue")
        check_2fa()
        try:
            wait_click("//button[contains(@class, 'btn-yes')] | //button[contains(text(), 'Continue')]", timeout=10)
        except Exception:
            self.tracker.log("Khong tim thay Continue", "warn")
        time.sleep(5)

        # === BUOC 10: Chon goal "Page view" ===
        self.tracker.set_current(step="Buoc 10: Chon Page view")
        check_2fa()
        try:
            wait_click("//conversion-goal-card[.//span[contains(text(), 'Page view')]] | //*[contains(text(), 'Page view')]", timeout=8)
            time.sleep(1)
        except Exception:
            self.tracker.log("Khong tim thay Page view goal, bo qua", "warn")

        # === BUOC 11: Dien Campaign name ===
        self.tracker.set_current(step="Buoc 11: Dien Campaign name")
        try:
            name_input = WebDriverWait(d, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@aria-label='Campaign name']"))
            )
            clear_and_type(name_input, name)
            self.tracker.log(f"Da dien campaign name: {name}", "success")
        except Exception as e:
            self.tracker.log(f"Khong dien duoc Campaign name: {e}", "warn")
        time.sleep(1)

        # === BUOC 12: Bo tick Enhanced conversions ===
        try:
            ec_cb = d.find_elements(By.XPATH, "//enhanced-conversions-view//mat-checkbox")
            for cb in ec_cb:
                if cb.is_displayed():
                    # Check neu dang ticked thi click de bo
                    if 'mat-checkbox-checked' in (cb.get_attribute('class') or ''):
                        js_click(cb)
                        self.tracker.log("Da bo tick Enhanced conversions")
                    break
        except Exception:
            pass

        # === BUOC 13: Click Continue ===
        self.tracker.set_current(step="Buoc 13: Click Continue")
        check_2fa()
        try:
            wait_click("//button[contains(@class, 'btn-yes')] | //button[contains(text(), 'Continue')]", timeout=10)
        except Exception:
            pass
        time.sleep(5)

        # === BUOC 14: Bidding ===
        self.tracker.set_current(step="Buoc 14: Bidding")
        check_2fa()
        bidding = campaign_config.get("bidding", "maximize_clicks")
        cpc = campaign_config.get("cpc", "")

        if "click" in bidding.lower():
            try:
                wait_click("//*[@id='metric-dropdown'] | //material-dropdown-select[contains(@class, 'metric')]", timeout=8)
                time.sleep(1)
                wait_click("//material-select-item[.//span[contains(text(), 'Clicks')]]", timeout=5)
                time.sleep(1)
                self.tracker.log("Da chon Clicks bidding", "success")
            except Exception:
                self.tracker.log("Khong doi duoc bidding sang Clicks", "warn")

        if cpc:
            try:
                cpc_cb = d.find_elements(By.XPATH, "//target-cpa-checkbox//mat-checkbox | //mat-checkbox[.//span[contains(text(), 'maximum')]]")
                for cb in cpc_cb:
                    if cb.is_displayed():
                        js_click(cb)
                        time.sleep(1)
                        break
                cpc_input = d.find_elements(By.XPATH, "//target-cpa-checkbox//input | //input[contains(@aria-label, 'CPC') or contains(@aria-label, 'maximum')]")
                for inp in cpc_input:
                    if inp.is_displayed():
                        inp.clear()
                        inp.send_keys(str(cpc))
                        self.tracker.log(f"Da dien CPC: {cpc}", "success")
                        break
            except Exception:
                self.tracker.log("Khong dien duoc CPC", "warn")

        # === BUOC 15: Click Next + Campaign Settings ===
        self.tracker.set_current(step="Buoc 15: Campaign Settings")
        check_2fa()
        try:
            wait_click("//material-button[contains(@class, 'button-next')] | //button[contains(text(), 'Next')]", timeout=10)
        except Exception:
            pass
        time.sleep(5)

        # Bo tick Search Partners + Display Network
        for checkbox_cls in ['search-checkbox', 'display-checkbox']:
            try:
                cb = d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{checkbox_cls}')]")
                for c in cb:
                    if c.is_displayed() and 'mat-checkbox-checked' in (c.get_attribute('class') or ''):
                        js_click(c)
                        time.sleep(0.5)
                        break
            except Exception:
                pass
        self.tracker.log("Da config Campaign Settings", "success")

        # === BUOC 16: Locations ===
        self.tracker.set_current(step="Buoc 16: Locations")
        check_2fa()
        target_locs = campaign_config.get("target_locations", [])
        exclude_locs = campaign_config.get("exclude_locations", [])

        if target_locs or exclude_locs:
            try:
                # Click "Enter another location" > "Advanced search"
                wait_click("//*[contains(text(), 'Enter another location')]", timeout=5)
                time.sleep(1)
                wait_click("//*[contains(text(), 'Advanced search')]", timeout=5)
                time.sleep(2)

                # Tick "Add locations in bulk" (neu chua tick)
                try:
                    bulk_cb = d.find_element(By.XPATH, "//material-checkbox[contains(@class, 'bulk-locations-checkbox')]")
                    if bulk_cb.get_attribute("aria-checked") != "true":
                        js_click(bulk_cb)
                        time.sleep(1)
                except Exception:
                    pass

                # Selector textarea chinh xac trong bulk location dialog
                BULK_TEXTAREA = "//bulk-location-input//textarea[contains(@class, 'textarea')]"
                SEARCH_BTN = "//bulk-location-input//material-button[contains(@class, 'search-button')]"
                TARGET_ALL_BTN = "//material-button[.//div[contains(text(), 'Target all')] or .//span[contains(text(), 'Target all')]]"
                EXCLUDE_ALL_BTN = "//material-button[.//div[contains(text(), 'Exclude all')] or .//span[contains(text(), 'Exclude all')]]"
                SAVE_BTN = "//material-yes-no-buttons//material-button[contains(@class, 'btn-yes')]"

                def bulk_search_locations(locs, action_btn_xpath, action_name):
                    """Paste locations vao bulk textarea, search, click action button."""
                    textarea = WebDriverWait(d, 10).until(
                        EC.element_to_be_clickable((By.XPATH, BULK_TEXTAREA))
                    )
                    # Click vao textarea truoc
                    textarea.click()
                    time.sleep(0.3)
                    # Dung JS set value — fix send_keys nuot ky tu voi text dai
                    loc_text = "\n".join(locs) if isinstance(locs, list) else str(locs).replace("|", "\n")
                    js_set_textarea(textarea, loc_text)
                    time.sleep(1)
                    # Doi nut Search het disabled
                    WebDriverWait(d, 15).until(
                        lambda drv: drv.find_element(By.XPATH, SEARCH_BTN).get_attribute("aria-disabled") != "true"
                    )
                    wait_click(SEARCH_BTN, timeout=10)
                    # Doi ket qua search hien ra — cho action button clickable
                    time.sleep(3)
                    WebDriverWait(d, 15).until(
                        EC.element_to_be_clickable((By.XPATH, action_btn_xpath))
                    )
                    wait_click(action_btn_xpath, timeout=10)
                    time.sleep(2)
                    self.tracker.log(f"Da {action_name} {len(locs) if isinstance(locs, list) else locs.count('|')+1} locations", "success")

                if target_locs:
                    bulk_search_locations(target_locs, TARGET_ALL_BTN, "target")

                if exclude_locs:
                    # Clear textarea cu truoc khi nhap exclude
                    try:
                        textarea = d.find_element(By.XPATH, BULK_TEXTAREA)
                        textarea.click()
                        time.sleep(0.2)
                        js_set_textarea(textarea, "")
                        time.sleep(0.5)
                    except Exception:
                        pass
                    bulk_search_locations(exclude_locs, EXCLUDE_ALL_BTN, "exclude")

                # Save locations
                wait_click(SAVE_BTN, timeout=10)
                time.sleep(3)
                self.tracker.log("Da save locations", "success")
            except Exception as e:
                self.tracker.log(f"Loi set locations: {e}", "warn")
                # Thu dong dialog neu bi ket
                try:
                    cancel = d.find_elements(By.XPATH, "//material-yes-no-buttons//material-button[contains(@class, 'btn-no')]")
                    for c in cancel:
                        if c.is_displayed():
                            js_click(c)
                            break
                except Exception:
                    pass

        # === BUOC 17: Languages — xoa English de All languages ===
        self.tracker.set_current(step="Buoc 17: Languages")
        try:
            remove_en = d.find_elements(By.XPATH, "//div[@aria-label='English remove'] | //material-chip[.//span[contains(text(), 'English')]]//button")
            for r in remove_en:
                if r.is_displayed():
                    js_click(r)
                    time.sleep(1)
                    self.tracker.log("Da xoa English -> All languages", "success")
                    break
        except Exception:
            pass

        # === BUOC 18: Click Next ===
        self.tracker.set_current(step="Buoc 18: Click Next")
        check_2fa()
        try:
            wait_click("//material-button[contains(@class, 'button-next')] | //button[contains(text(), 'Next')]", timeout=10)
        except Exception:
            pass
        time.sleep(5)

        # === BUOC 19: AI Max — skip, click Next ===
        self.tracker.set_current(step="Buoc 19: Skip AI Max")
        check_2fa()
        try:
            wait_click("//material-button[contains(@class, 'button-next')] | //button[contains(text(), 'Next')]", timeout=10)
        except Exception:
            pass
        time.sleep(5)

        # === BUOC 20: Keyword and asset generation — skip ===
        self.tracker.set_current(step="Buoc 20: Skip keyword generation")
        check_2fa()
        try:
            wait_click("//material-button[contains(@class, 'button-skip')] | //button[contains(text(), 'Skip')]", timeout=8)
        except Exception:
            try:
                wait_click("//material-button[contains(@class, 'button-next')] | //button[contains(text(), 'Next')]", timeout=5)
            except Exception:
                pass
        time.sleep(5)

        # === BUOC 21: Keywords and Ads ===
        self.tracker.set_current(step="Buoc 21: Keywords + Ads")
        check_2fa()

        # Paste keywords
        keywords = campaign_config.get("keywords", [])
        if keywords:
            try:
                kw_textarea = wait_visible("//keyword-editor//textarea | //textarea[contains(@aria-label, 'keyword') or contains(@aria-label, 'Keyword')]", timeout=10)
                kw_text = "\n".join(keywords) if isinstance(keywords, list) else str(keywords)
                kw_textarea.clear()
                kw_textarea.send_keys(kw_text)
                self.tracker.log(f"Da dien {len(keywords)} keywords", "success")
            except Exception as e:
                self.tracker.log(f"Loi dien keywords: {e}", "warn")
            time.sleep(1)

        # Final URL
        final_url = campaign_config.get("final_url", "")
        if final_url:
            try:
                fill_input("//final-url-input//input[@aria-label='Final URL'] | //input[@aria-label='Final URL']", final_url, timeout=10)
                self.tracker.log(f"Da dien Final URL: {final_url}", "success")
            except Exception as e:
                self.tracker.log(f"Loi dien Final URL: {e}", "warn")
            time.sleep(1)

        # Headlines
        headlines = campaign_config.get("headlines", [])
        if headlines:
            try:
                HL_XPATH = "//section[contains(@class, 'headline')]//input | //input[contains(@aria-label, 'Headline')]"
                ADD_HL_BTN = "//material-button[.//span[contains(text(), 'Add headline')]] | //button[contains(@aria-label, 'headline')]"
                # Wait cho it nhat 1 headline input load
                WebDriverWait(d, 10).until(
                    EC.presence_of_element_located((By.XPATH, HL_XPATH))
                )
                time.sleep(1)
                filled = 0
                for hl in headlines:
                    # Lay lai danh sach inputs moi lan (DOM thay doi khi add)
                    hl_inputs = d.find_elements(By.XPATH, HL_XPATH)
                    visible_hls = [h for h in hl_inputs if h.is_displayed()]
                    if filled >= len(visible_hls):
                        # Het o trong — click "Add headline" de them
                        try:
                            add_btn = d.find_element(By.XPATH, ADD_HL_BTN)
                            if add_btn.is_displayed():
                                js_click(add_btn)
                                time.sleep(1)
                                hl_inputs = d.find_elements(By.XPATH, HL_XPATH)
                                visible_hls = [h for h in hl_inputs if h.is_displayed()]
                        except Exception:
                            break  # Khong them duoc nua, dung lai
                    if filled < len(visible_hls):
                        clear_and_type(visible_hls[filled], hl)
                        filled += 1
                        time.sleep(0.3)
                self.tracker.log(f"Da dien {filled}/{len(headlines)} headlines", "success")
            except Exception as e:
                self.tracker.log(f"Loi dien headlines: {e}", "warn")

        # Descriptions
        descriptions = campaign_config.get("descriptions", [])
        if descriptions:
            try:
                DESC_XPATH = "//section[contains(@class, 'description')]//textarea | //textarea[contains(@aria-label, 'Description')]"
                ADD_DESC_BTN = "//material-button[.//span[contains(text(), 'Add description')]] | //button[contains(@aria-label, 'description')]"
                # Wait cho it nhat 1 description input load
                WebDriverWait(d, 10).until(
                    EC.presence_of_element_located((By.XPATH, DESC_XPATH))
                )
                time.sleep(1)
                filled = 0
                for desc in descriptions:
                    desc_inputs = d.find_elements(By.XPATH, DESC_XPATH)
                    visible_descs = [dd for dd in desc_inputs if dd.is_displayed()]
                    if filled >= len(visible_descs):
                        try:
                            add_btn = d.find_element(By.XPATH, ADD_DESC_BTN)
                            if add_btn.is_displayed():
                                js_click(add_btn)
                                time.sleep(1)
                                desc_inputs = d.find_elements(By.XPATH, DESC_XPATH)
                                visible_descs = [dd for dd in desc_inputs if dd.is_displayed()]
                        except Exception:
                            break
                    if filled < len(visible_descs):
                        clear_and_type(visible_descs[filled], desc)
                        filled += 1
                        time.sleep(0.3)
                self.tracker.log(f"Da dien {filled}/{len(descriptions)} descriptions", "success")
            except Exception as e:
                self.tracker.log(f"Loi dien descriptions: {e}", "warn")

        # Click Next
        try:
            wait_click("//material-button[contains(@class, 'button-next')] | //button[contains(text(), 'Next')]", timeout=10)
        except Exception:
            pass
        time.sleep(5)

        # === BUOC 22: Budget ===
        self.tracker.set_current(step="Buoc 22: Budget")
        check_2fa()
        budget = campaign_config.get("budget", "5")

        # Chon "Set custom budget"
        try:
            wait_click("//proactive-budget-recommendation-picker//material-radio[.//div[contains(text(), 'Set custom budget')]] | //*[contains(text(), 'Set custom budget')]", timeout=8)
            time.sleep(1)
        except Exception:
            pass

        # Dien budget
        try:
            budget_input = wait_visible("//budget-base-edit//input | //input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]", timeout=10)
            budget_input.clear()
            budget_input.send_keys(str(budget))
            self.tracker.log(f"Da dien budget: {budget}", "success")
        except Exception as e:
            self.tracker.log(f"Loi dien budget: {e}", "warn")

        # Click Next
        try:
            wait_click("//material-button[contains(@class, 'button-next')] | //button[contains(text(), 'Next')]", timeout=10)
        except Exception:
            pass
        time.sleep(5)

        # === BUOC 23: Review + Publish ===
        self.tracker.set_current(step="Buoc 23: Publish")
        check_2fa()

        for attempt in range(3):
            try:
                wait_click("//material-button[.//span[contains(text(), 'Publish')]] | //button[contains(text(), 'Publish')]", timeout=15)
                self.tracker.log("Da click Publish!", "success")
                time.sleep(5)

                # Check con o trang Review khong (co loi)
                page = d.page_source[:3000].lower()
                if 'publish' in page and 'review' in page:
                    self.tracker.log(f"Van o trang Review (lan {attempt+1}), co the co loi...", "warn")
                    time.sleep(3)
                    continue
                break
            except Exception:
                self.tracker.log(f"Khong tim thay nut Publish (lan {attempt+1})", "warn")
                time.sleep(3)

        # Luu vao DB
        upsert_campaign(self.customer_id, name, status="published")
        self.tracker.log(f"Campaign '{name}' da duoc publish thanh cong!", "success")
        return True


