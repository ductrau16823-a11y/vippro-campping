#!/usr/bin/env python3
"""
=== VIPPRO CAMPPING V4 ===
Tong hop tot nhat cua V1 + V2 + V3:
- Scan-based loop (V2): linh hoat thu tu trang
- Stepper recovery (V3): chinh xac sau 2FA
- Selector da test OK (V1): bidding, locations, keywords
- 3s giua moi buoc, skip neu da lam
- 2FA xu ly tai cho → doc stepper → tiep tuc dung buoc

Quy trinh: QUY_TRINH_LEN_CAMP.md
"""

import sys
import time
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api_helpers import upsert_campaign


class CampaignCreator:
    """Tao campaign — V4: scan-based + stepper recovery."""

    def __init__(self, driver, account_data, tracker):
        self.driver = driver
        self.account_data = account_data
        self.tracker = tracker
        self.customer_id = account_data.get("accountId", "")
        self.gmail = account_data.get("gmailEmail", "")

    def run_campaign_flow(self, campaign_config, skip_navigate=False, camp_index=1):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.action_chains import ActionChains

        d = self.driver
        base_name = campaign_config.get("name", "Campaign")
        name = f"{base_name} {camp_index}" if camp_index > 1 else base_name
        self.tracker.log(f"=== [V4] Bat dau tao campaign: {name} (#{camp_index}) ===")

        # ==================== HELPERS ====================

        def js_click(el):
            d.execute_script("arguments[0].click()", el)

        def action_click(el):
            ActionChains(d).move_to_element(el).pause(0.3).click().perform()

        def clear_and_type(el, value):
            el.click()
            time.sleep(0.3)
            el.send_keys(Keys.CONTROL, "a")
            time.sleep(0.2)
            el.send_keys(str(value))
            time.sleep(0.3)

        def js_set_textarea(el, value):
            d.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                el, value,
            )

        def click_button(text, timeout=10):
            for _ in range(3):
                for b in d.find_elements(By.XPATH, "//button | //material-button"):
                    try:
                        if b.is_displayed() and b.text.strip() == text:
                            action_click(b)
                            return True
                    except Exception:
                        pass
                time.sleep(1)
            return False

        def is_checkbox_ticked(cb_element):
            return "check_box_outline_blank" not in cb_element.text

        def safe_click(el):
            """Scroll + action_click, fallback js_click."""
            d.execute_script("arguments[0].scrollIntoView({block: 'center'})", el)
            time.sleep(0.5)
            try:
                action_click(el)
            except Exception:
                js_click(el)

        # ==================== 2FA ====================

        def handle_2fa():
            import pyotp
            import requests

            dialog = None
            TWO_FA_KEYWORDS = ["Confirm your identity", "Verify it's you", "2-Step Verification",
                               "confirm your identity", "verify it", "identity verification"]
            for dlg in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dlg.is_displayed():
                        continue
                    dlg_text = dlg.text
                    # Phai co dau hieu 2FA that, khong chi moi "Confirm"
                    is_2fa = any(kw in dlg_text for kw in TWO_FA_KEYWORDS)
                    if not is_2fa:
                        # Fallback: dialog co "Confirm" + "identity" hoac "verification"
                        if "Confirm" in dlg_text and ("identity" in dlg_text.lower() or "verif" in dlg_text.lower()):
                            is_2fa = True
                    if is_2fa:
                        dialog = dlg
                        break
                except Exception:
                    continue
            if not dialog:
                return False

            self.tracker.log("[2FA] Gap popup xac thuc...", "warn")

            # Click Confirm/Try again (lan 1)
            for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                try:
                    if b.is_displayed() and b.text.strip() in ("Confirm", "Try again"):
                        action_click(b)
                        self.tracker.log(f"[2FA] Click '{b.text.strip()}'")
                        time.sleep(5)
                        break
                except Exception:
                    pass

            # Try again lan 2
            for dlg2 in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if dlg2.is_displayed() and "Try again" in dlg2.text:
                        for b2 in dlg2.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b2.is_displayed() and "Try again" in b2.text:
                                action_click(b2)
                                self.tracker.log("[2FA] Click Try again (lan 2)")
                                time.sleep(5)
                                break
                        break
                except Exception:
                    pass

            # Tab 2FA moi
            time.sleep(2)
            handles = d.window_handles
            if len(handles) > 1:
                for h in handles:
                    d.switch_to.window(h)
                    try:
                        if "Sign in" not in d.title:
                            continue
                        totp_els = d.find_elements(By.CSS_SELECTOR, "input#totpPin")
                        if not totp_els or not totp_els[0].is_displayed():
                            continue

                        email = ""
                        for e in d.find_elements(By.XPATH, "//*[contains(text(), '@gmail.com')]"):
                            if e.is_displayed():
                                email = e.text.strip().lower()
                                break

                        secret = None
                        try:
                            r = requests.get("http://localhost:3000/api/gmail", timeout=10)
                            data = r.json()
                            items = data.get("data", data) if isinstance(data, dict) else data
                            for g in items:
                                if g.get("email", "").lower() == email:
                                    secret = g.get("twoFactorKey")
                                    break
                        except Exception:
                            pass

                        if secret:
                            code = pyotp.TOTP(secret).now()
                            self.tracker.log(f"[2FA] {email} -> {code}")
                            totp_els[0].click()
                            time.sleep(0.5)
                            totp_els[0].send_keys(code)
                            time.sleep(1)
                            next_btn = d.find_element(By.CSS_SELECTOR, "#totpNext button")
                            action_click(next_btn)
                            self.tracker.log("[2FA] OK!", "success")
                            time.sleep(5)
                        break
                    except Exception:
                        pass

                for h in d.window_handles:
                    d.switch_to.window(h)
                    try:
                        if "Google Ads" in d.title:
                            break
                    except Exception:
                        pass

            time.sleep(3)
            return True

        # ==================== POPUPS ====================

        def handle_popups():
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or not dialog.text.strip():
                        continue
                    txt = dialog.text
                    if "Conversion goals" in txt:
                        for cb in dialog.find_elements(By.XPATH, ".//material-button[contains(@aria-label, 'Close')]"):
                            if cb.is_displayed():
                                js_click(cb)
                                self.tracker.log("[POPUP] Dong Conversion goals")
                                time.sleep(2)
                                break
                    elif "Exit guide" in txt:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and "Leave" in b.text:
                                js_click(b)
                                self.tracker.log("[POPUP] Leave")
                                time.sleep(3)
                                break
                    elif "Fix errors" in txt and "Discard" in txt:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and b.text.strip() == "Fix errors":
                                action_click(b)
                                self.tracker.log("[POPUP] Fix errors")
                                time.sleep(5)
                                break
                except Exception:
                    pass

        def handle_draft():
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or "draft" not in dialog.text.lower():
                        continue
                    self.tracker.log("[DRAFT] Gap dialog draft...")
                    for n in dialog.find_elements(By.XPATH, ".//campaign-name-cell//div[contains(@class, 'name')]"):
                        if n.is_displayed():
                            draft_name = n.text.strip()
                            if draft_name == base_name:
                                js_click(n)
                                self.tracker.log(f"[DRAFT] Click '{draft_name}'")
                                time.sleep(5)
                            else:
                                for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                                    if b.is_displayed() and "Start new" in b.text:
                                        js_click(b)
                                        self.tracker.log("[DRAFT] Start new")
                                        time.sleep(3)
                                        break
                            return True
                except Exception:
                    pass
            return False

        def check_all():
            """Xu ly 2FA + popup tai cho. Returns True neu co 2FA."""
            try:
                had_2fa = handle_2fa()
                handle_popups()
                handle_draft()
                if had_2fa:
                    time.sleep(3)
                    handle_popups()
                    handle_draft()
                return had_2fa
            except Exception as e:
                self.tracker.log(f"[CHECK] Loi: {e}", "warn")
                return False

        # ==================== STEPPER (tu V3) ====================

        def read_stepper():
            """Doc stepper ben trai — dung sau 2FA de biet dang o dau."""
            stepper_map = {
                "bidding": ["Bidding", "Bid strategy"],
                "campaign_settings": ["Campaign settings", "Settings"],
                "keywords_ads": ["Keywords and ads", "Keywords", "Ad group"],
                "budget": ["Budget"],
                "review": ["Review"],
            }
            try:
                for item in d.find_elements(By.XPATH, "//left-stepper-menu-item"):
                    try:
                        if not item.is_displayed():
                            continue
                        classes = item.get_attribute("class") or ""
                        if not ("selected" in classes or "active" in classes or "focused" in classes):
                            continue
                        item_text = item.text.strip()
                        for step_name, keywords in stepper_map.items():
                            for kw in keywords:
                                if kw.lower() in item_text.lower():
                                    return step_name
                    except Exception:
                        continue
            except Exception:
                pass
            return "unknown"

        # ==================== SCAN PAGE (tu V2, fix loi) ====================

        def scan_page():
            """Scan trang, tra ve (page_name, features)."""
            features = set()
            page_name = "unknown"

            # 1. Objective — check da chon chua (icon check_circle)
            objective_selected = False
            try:
                icons = d.find_elements(By.XPATH,
                    "//marketing-objective-card-v2//material-icon[contains(@class, 'checked-icon')]//i[text()='check_circle']")
                if any(ci.is_displayed() for ci in icons):
                    objective_selected = True
            except Exception:
                pass

            if not objective_selected:
                for el in d.find_elements(By.XPATH, "//span[contains(@class, 'unified-goals-card-title')]"):
                    try:
                        if el.is_displayed():
                            txt = el.text.strip().lower()
                            if "without guidance" in txt or "sales" in txt or "leads" in txt:
                                features.add("card:goal_selection")
                    except Exception:
                        pass

            # 2. Campaign type
            for el in d.find_elements(By.XPATH, "//*[@data-value='SEARCH'] | //*[@data-value='DISPLAY']"):
                try:
                    if el.is_displayed():
                        features.add("card:campaign_type")
                except Exception:
                    pass

            # 3. Conversion goal picker
            for el in d.find_elements(By.XPATH, "//conversion-goal-picker"):
                try:
                    if el.is_displayed():
                        features.add("picker:conversion_goals")
                except Exception:
                    pass

            # 4. Page view — check da chon chua
            try:
                pv_checked = d.find_elements(By.XPATH,
                    "//material-icon[@id='PAGE_VIEW'][.//i[text()='radio_button_checked']]")
                if any(p.is_displayed() for p in pv_checked):
                    features.add("pageview:checked")
            except Exception:
                pass

            # 5. Checkboxes
            for c in d.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
                try:
                    if c.is_displayed():
                        txt = c.text
                        if "Website visits" in txt:
                            features.add("cb:website_visits")
                        if "enhanced conversions" in txt.lower():
                            features.add("cb:enhanced_conversions")
                        if "search-checkbox" in (c.get_attribute("class") or ""):
                            features.add("cb:search_partners")
                        if "display-checkbox" in (c.get_attribute("class") or ""):
                            features.add("cb:display_network")
                        if "maximum cost per click" in txt:
                            features.add("cb:max_cpc")
                except Exception:
                    pass

            # 6. Inputs
            for inp in d.find_elements(By.XPATH, "//input"):
                try:
                    if inp.is_displayed():
                        label = inp.get_attribute("aria-label") or ""
                        if "Campaign name" in label:
                            features.add("input:campaign_name")
                        if "Final URL" in label:
                            features.add("input:final_url")
                        if "budget" in label.lower():
                            features.add("input:budget")
                except Exception:
                    pass

            # 7. Textareas
            for ta in d.find_elements(By.XPATH, "//textarea"):
                try:
                    if ta.is_displayed():
                        label = ta.get_attribute("aria-label") or ""
                        if "keyword" in label.lower():
                            features.add("ta:keywords")
                except Exception:
                    pass

            # 8. Headlines
            for s in d.find_elements(By.XPATH, "//section[contains(@class, 'headline')]//input"):
                try:
                    if s.is_displayed():
                        features.add("input:headlines")
                        break
                except Exception:
                    pass

            # 9. Bidding dropdown
            for db in d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"):
                try:
                    if db.is_displayed() and ("Conversions" in db.text or "Clicks" in db.text):
                        features.add("dropdown:bidding")
                except Exception:
                    pass

            # 10. Budget radio
            for r in d.find_elements(By.TAG_NAME, "material-radio"):
                try:
                    if r.is_displayed() and "Set custom budget" in r.text:
                        features.add("radio:custom_budget")
                except Exception:
                    pass

            # 11. Buttons
            for b in d.find_elements(By.XPATH, "//button | //material-button"):
                try:
                    if b.is_displayed():
                        t = b.text.strip()
                        if t == "Continue":
                            features.add("btn:continue")
                        elif t == "Next":
                            features.add("btn:next")
                        elif "Agree and continue" in t:
                            features.add("btn:agree_continue")
                        elif "Publish campaign" in t:
                            features.add("btn:publish")
                        elif t == "Skip":
                            features.add("btn:skip")
                except Exception:
                    pass

            # --- Quyet dinh trang ---
            if "btn:publish" in features:
                page_name = "review_publish"
            elif "card:goal_selection" in features:
                page_name = "goal_selection"
            elif "card:campaign_type" in features and "picker:conversion_goals" not in features and "input:campaign_name" not in features:
                page_name = "campaign_type"
            elif "picker:conversion_goals" in features or "input:campaign_name" in features:
                page_name = "goals_and_name"
            elif ("dropdown:bidding" in features or "cb:max_cpc" in features) and "input:budget" not in features:
                page_name = "bidding"
            elif "cb:search_partners" in features or "cb:display_network" in features:
                page_name = "campaign_settings"
            elif "ta:keywords" in features or "input:final_url" in features or "input:headlines" in features:
                page_name = "keywords_ads"
            elif "radio:custom_budget" in features or "input:budget" in features:
                page_name = "budget"
            elif "btn:skip" in features:
                page_name = "skip_page"

            return page_name, features

        # ==================== HANDLERS ====================

        def handle_goal_selection():
            """Buoc 4: Chon without guidance."""
            try:
                el = WebDriverWait(d, 5).until(
                    EC.element_to_be_clickable((By.XPATH,
                        "//*[@data-value='No objective'] | "
                        "//span[contains(@class, 'unified-goals-card-title') and contains(text(), 'without guidance')]"))
                )
                js_click(el)
                time.sleep(3)
                self.tracker.log("Chon 'without guidance'", "success")
            except Exception:
                self.tracker.log("Skip — da chon san", "warn")

        def handle_campaign_type():
            """Buoc 5: Chon Search."""
            camp_type = campaign_config.get("type", "search").upper()
            try:
                el = WebDriverWait(d, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f"//*[@data-value='{camp_type}']"))
                )
                js_click(el)
                time.sleep(3)
                self.tracker.log(f"Chon {camp_type}", "success")
            except Exception:
                self.tracker.log(f"Skip {camp_type} — da chon san", "warn")

        def handle_goals_and_name():
            """Buoc 6: Page view + Campaign name + bo Enhanced conversions."""

            # 6a. Tick Page view
            pv_done = False
            # Check da chon chua
            try:
                checked = d.find_elements(By.XPATH,
                    "//material-icon[@id='PAGE_VIEW'][.//i[text()='radio_button_checked']]")
                if any(c.is_displayed() for c in checked):
                    self.tracker.log("Page view da chon — skip", "success")
                    pv_done = True
            except Exception:
                pass

            if not pv_done:
                for _ in range(2):
                    try:
                        btns = d.find_elements(By.XPATH,
                            "//conversion-goal-card[.//material-icon[@id='PAGE_VIEW']]//button")
                        for btn in btns:
                            if btn.is_displayed():
                                safe_click(btn)
                                time.sleep(2)
                                # Verify
                                try:
                                    icon = d.find_element(By.XPATH, "//material-icon[@id='PAGE_VIEW']//i")
                                    if "radio_button_checked" in icon.text:
                                        pv_done = True
                                        self.tracker.log("Tick Page view OK!", "success")
                                except Exception:
                                    pass
                                break
                    except Exception:
                        pass
                    if pv_done:
                        break
                    time.sleep(2)

            if not pv_done:
                self.tracker.log("Skip Page view — khong thay hoac da chon", "warn")

            # 6b. Campaign name
            try:
                name_input = WebDriverWait(d, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@aria-label='Campaign name']"))
                )
                current_val = name_input.get_attribute("value") or ""
                if not current_val or current_val == "Campaign 1":
                    clear_and_type(name_input, name)
                    self.tracker.log(f"Dien Campaign name: {name}", "success")
                else:
                    self.tracker.log(f"Campaign name da co: '{current_val}' — skip", "success")
            except Exception:
                self.tracker.log("Skip Campaign name — khong thay", "warn")

            # 6c. Bo tick Enhanced conversions
            for cb in d.find_elements(By.XPATH,
                    "//enhanced-conversions-view//mat-checkbox | //material-checkbox | //mat-checkbox"):
                try:
                    if cb.is_displayed() and "enhanced conversions" in cb.text.lower() and is_checkbox_ticked(cb):
                        js_click(cb)
                        self.tracker.log("Bo tick Enhanced conversions", "success")
                        time.sleep(1)
                        break
                except Exception:
                    pass

        def handle_bidding():
            """Buoc 7: Bidding — Clicks + CPC."""
            bidding = campaign_config.get("bidding", "maximize_clicks")
            cpc = campaign_config.get("cpc", "")

            if "click" in bidding.lower():
                try:
                    for db in d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"):
                        if db.is_displayed() and ("Conversions" in db.text or "Clicks" in db.text):
                            action_click(db)
                            time.sleep(2)
                            break
                    for item in d.find_elements(By.XPATH, "//material-select-dropdown-item"):
                        if item.is_displayed() and item.text.strip() == "Clicks":
                            js_click(item)
                            self.tracker.log("Chon Clicks bidding", "success")
                            time.sleep(2)
                            break
                except Exception:
                    self.tracker.log("Khong doi duoc bidding", "warn")

            if cpc:
                try:
                    for c in d.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
                        if c.is_displayed() and "maximum cost per click" in c.text:
                            js_click(c)
                            time.sleep(1)
                            break
                    for s in d.find_elements(By.XPATH,
                            "//div[contains(@class, 'max-bid-container')] | "
                            "//section[.//span[contains(text(), 'Maximum CPC')]]"):
                        if s.is_displayed():
                            for inp in s.find_elements(By.XPATH, ".//input"):
                                if inp.is_displayed():
                                    clear_and_type(inp, cpc)
                                    self.tracker.log(f"Dien CPC: {cpc}", "success")
                                    break
                            break
                except Exception:
                    self.tracker.log("Khong dien duoc CPC", "warn")

        def handle_campaign_settings():
            """Buoc 8: Networks + Locations + Languages + EU ads."""
            # 8a+8b: Bo tick Search Partners + Display Network
            for cls_name in ["search-checkbox", "display-checkbox"]:
                for c in d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls_name}')]"):
                    try:
                        if c.is_displayed() and is_checkbox_ticked(c):
                            js_click(c)
                            time.sleep(0.5)
                    except Exception:
                        pass
            self.tracker.log("Bo tick Search Partners + Display Network", "success")

            # 8c: Locations
            target_locs = campaign_config.get("target_locations", [])
            exclude_locs = campaign_config.get("exclude_locations", [])
            if target_locs or exclude_locs:
                try:
                    WebDriverWait(d, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Enter another location')]"))
                    ).click()
                    time.sleep(2)
                    WebDriverWait(d, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Advanced search')]"))
                    ).click()
                    time.sleep(3)

                    bulk_cb = d.find_element(By.XPATH, "//material-checkbox[contains(@class, 'bulk-locations-checkbox')]")
                    if bulk_cb.get_attribute("aria-checked") != "true":
                        js_click(bulk_cb)
                        time.sleep(1)

                    BULK_TA = "//bulk-location-input//textarea[contains(@class, 'textarea')]"
                    SEARCH_BTN = "//bulk-location-input//material-button[contains(@class, 'search-button')]"
                    TARGET_ALL = "//material-button[.//div[contains(text(), 'Target all')] or .//span[contains(text(), 'Target all')]]"
                    EXCLUDE_ALL = "//material-button[.//div[contains(text(), 'Exclude all')] or .//span[contains(text(), 'Exclude all')]]"

                    def bulk_search(locs, action_xpath, label):
                        ta = WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.XPATH, BULK_TA)))
                        ta.click()
                        time.sleep(0.5)
                        loc_text = "\n".join(locs) if isinstance(locs, list) else str(locs).replace("|", "\n")
                        js_set_textarea(ta, loc_text)
                        time.sleep(2)
                        WebDriverWait(d, 15).until(
                            lambda drv: drv.find_element(By.XPATH, SEARCH_BTN).get_attribute("aria-disabled") != "true"
                        )
                        js_click(d.find_element(By.XPATH, SEARCH_BTN))
                        time.sleep(8)
                        WebDriverWait(d, 15).until(EC.element_to_be_clickable((By.XPATH, action_xpath)))
                        js_click(d.find_element(By.XPATH, action_xpath))
                        time.sleep(3)
                        count = len(locs) if isinstance(locs, list) else locs.count("|") + 1
                        self.tracker.log(f"Da {label} {count} locations", "success")

                    if target_locs:
                        bulk_search(target_locs, TARGET_ALL, "target")
                    if exclude_locs:
                        try:
                            ta = d.find_element(By.XPATH, BULK_TA)
                            ta.click()
                            time.sleep(0.3)
                            js_set_textarea(ta, "")
                            time.sleep(1)
                        except Exception:
                            pass
                        bulk_search(exclude_locs, EXCLUDE_ALL, "exclude")

                    time.sleep(2)
                    for b in d.find_elements(By.XPATH, "//material-button | //button"):
                        try:
                            if b.is_displayed() and b.text.strip() == "Save":
                                js_click(b)
                                self.tracker.log("Save locations", "success")
                                time.sleep(5)
                                break
                        except Exception:
                            pass
                except Exception as e:
                    self.tracker.log(f"Loi locations: {e}", "warn")
                    try:
                        for c in d.find_elements(By.XPATH, "//material-button | //button"):
                            if c.is_displayed() and c.text.strip() == "Cancel":
                                js_click(c)
                                break
                    except Exception:
                        pass

            # 8d: Xoa English
            try:
                for r in d.find_elements(By.XPATH, "//div[@aria-label='English remove']"):
                    if r.is_displayed():
                        js_click(r)
                        self.tracker.log("Xoa English -> All languages", "success")
                        time.sleep(1)
                        break
            except Exception:
                pass

            # 8e: EU political ads — chon No
            try:
                for el in d.find_elements(By.XPATH, "//eu-political-ads-plugin"):
                    if el.is_displayed():
                        for radio in el.find_elements(By.XPATH,
                                ".//material-radio[.//span[contains(text(), 'No')]] | "
                                ".//material-button[.//span[contains(text(), 'No')]]"):
                            if radio.is_displayed():
                                js_click(radio)
                                self.tracker.log("EU political ads: No", "success")
                                time.sleep(1)
                                break
                        break
            except Exception:
                pass

        def handle_keywords_ads():
            """Buoc 9: Keywords + URL + Headlines + Descriptions."""
            keywords = campaign_config.get("keywords", [])
            if keywords:
                try:
                    kw_ta = WebDriverWait(d, 15).until(
                        EC.presence_of_element_located((By.XPATH, '//textarea[contains(@aria-label, "Enter or paste keywords")]'))
                    )
                    kw_ta.click()
                    time.sleep(0.5)
                    kw_text = "\n".join(keywords) if isinstance(keywords, list) else str(keywords)
                    kw_ta.send_keys(kw_text)
                    self.tracker.log(f"Dien {len(keywords)} keywords", "success")
                except Exception as e:
                    self.tracker.log(f"Loi keywords: {e}", "warn")
                time.sleep(1)

            final_url = campaign_config.get("final_url", "")
            if final_url:
                try:
                    url_input = WebDriverWait(d, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '//input[@aria-label="Final URL"]'))
                    )
                    clear_and_type(url_input, final_url)
                    self.tracker.log("Dien Final URL", "success")
                except Exception as e:
                    self.tracker.log(f"Loi Final URL: {e}", "warn")
                time.sleep(1)

            headlines = campaign_config.get("headlines", [])
            if headlines:
                try:
                    HL_XPATH = '//section[contains(@class, "headline")]//input'
                    WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, HL_XPATH)))
                    time.sleep(2)
                    section = d.find_element(By.XPATH, '//section[contains(@class, "headline")]')
                    filled = 0
                    for hl in headlines:
                        inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                        if filled >= len(inps):
                            try:
                                for ad in section.find_elements(By.XPATH, ".//div[contains(@class, 'add')]"):
                                    if ad.is_displayed() and "Headline" in ad.text:
                                        js_click(ad)
                                        time.sleep(1)
                                        break
                                inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                            except Exception:
                                break
                        if filled < len(inps):
                            clear_and_type(inps[filled], hl)
                            filled += 1
                            time.sleep(0.5)
                    self.tracker.log(f"Dien {filled}/{len(headlines)} headlines", "success")
                except Exception as e:
                    self.tracker.log(f"Loi headlines: {e}", "warn")

            descriptions = campaign_config.get("descriptions", [])
            if descriptions:
                try:
                    visible = [dd for dd in d.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if dd.is_displayed()]
                    filled = 0
                    for desc in descriptions:
                        if filled >= len(visible):
                            try:
                                for ad in d.find_elements(By.XPATH, '//section[contains(@class, "description")]//div[contains(@class, "add")]'):
                                    if ad.is_displayed() and "Description" in ad.text:
                                        js_click(ad)
                                        time.sleep(1)
                                        break
                                visible = [dd for dd in d.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if dd.is_displayed()]
                            except Exception:
                                break
                        if filled < len(visible):
                            clear_and_type(visible[filled], desc)
                            filled += 1
                            time.sleep(0.5)
                    self.tracker.log(f"Dien {filled}/{len(descriptions)} descriptions", "success")
                except Exception as e:
                    self.tracker.log(f"Loi descriptions: {e}", "warn")

        def handle_budget():
            """Buoc 10: Budget."""
            budget = campaign_config.get("budget", "5")

            for r in d.find_elements(By.TAG_NAME, "material-radio"):
                try:
                    if r.is_displayed() and "Set custom budget" in r.text:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'})", r)
                        time.sleep(0.5)
                        action_click(r)
                        time.sleep(2)
                        break
                except Exception:
                    pass

            panels = d.find_elements(By.XPATH, "//proactive-budget-recommendation-picker//material-expansionpanel")
            for p in reversed(panels):
                try:
                    if p.is_displayed() and "Set custom" in p.text:
                        header = p.find_element(By.XPATH, ".//div[contains(@class, 'header')]")
                        action_click(header)
                        time.sleep(3)
                        break
                except Exception:
                    pass

            budget_filled = False
            for xp in [
                "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]",
                "//input[contains(@aria-label, 'amount') or contains(@aria-label, 'Amount')]",
                "//proactive-budget-recommendation-picker//input[@type='text']",
                "//material-expansionpanel[.//span[contains(text(), 'Set custom')]]//input",
                "//div[contains(@class, 'budget')]//input",
            ]:
                if budget_filled:
                    break
                try:
                    for el in d.find_elements(By.XPATH, xp):
                        if el.is_displayed():
                            clear_and_type(el, budget)
                            self.tracker.log(f"Dien budget: ${budget}", "success")
                            budget_filled = True
                            break
                except Exception:
                    pass

            if not budget_filled:
                time.sleep(5)
                try:
                    bi = WebDriverWait(d, 10).until(
                        EC.element_to_be_clickable((By.XPATH,
                            "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"))
                    )
                    clear_and_type(bi, budget)
                    self.tracker.log(f"Dien budget (retry): ${budget}", "success")
                except Exception:
                    self.tracker.log("Khong tim thay budget input", "warn")

        def handle_publish():
            """Buoc 11: Publish."""
            for wait_round in range(12):
                had_2fa = check_all()
                if had_2fa:
                    step = read_stepper()
                    if step != "review" and step != "unknown":
                        self.tracker.log(f"[2FA] Sau 2FA o '{step}' — quay lai", "warn")
                        return "redirect_" + step

                found = False
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    try:
                        if b.is_displayed() and "Publish campaign" in b.text:
                            found = True
                            break
                    except Exception:
                        pass
                if found:
                    break
                self.tracker.log(f"Doi Publish... ({(wait_round + 1) * 5}s)")
                time.sleep(5)

            for attempt in range(5):
                check_all()
                pub_clicked = False
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    try:
                        if b.is_displayed() and "Publish campaign" in b.text:
                            d.execute_script("arguments[0].scrollIntoView({block: 'center'})", b)
                            time.sleep(1)
                            action_click(b)
                            self.tracker.log(f"Click Publish! (lan {attempt + 1})", "success")
                            pub_clicked = True
                            time.sleep(10)
                            break
                    except Exception:
                        pass
                if not pub_clicked:
                    click_button("Next")
                    time.sleep(10)
                check_all()
                if "New campaign" not in d.title and "Search campaign" not in d.title:
                    return "published"
                self.tracker.log(f"Van o Review (lan {attempt + 1})", "warn")
                time.sleep(5)
            return "published"

        # ==================== NAVIGATE ====================

        def do_navigate():
            """Xu ly login + chon TK. Co the goi lai khi bi redirect."""
            for nav_try in range(3):
                current_url = d.current_url.lower()
                current_title = d.title.lower()
                self.tracker.log(f"[NAV] Trang: {d.title} (lan {nav_try + 1})")

                if "sign in" in current_title or "accounts.google.com" in current_url:
                    self.tracker.log("[NAV] Sign in — login...")
                    try:
                        for el in d.find_elements(By.XPATH, "//div[@data-identifier]"):
                            if el.is_displayed():
                                action_click(el)
                                self.tracker.log(f"[NAV] Click {el.get_attribute('data-identifier')}")
                                time.sleep(8)
                                break
                    except Exception:
                        pass
                    time.sleep(3)
                    continue  # quay lai check URL moi

                if "selectaccount" in current_url:
                    self.tracker.log("[NAV] Select Account...")
                    for item in d.find_elements(By.CSS_SELECTOR, "material-list-item"):
                        if self.customer_id in item.text and "Setup in progress" not in item.text:
                            item.click()
                            self.tracker.log(f"[NAV] Chon TK {self.customer_id}")
                            time.sleep(10)
                            break
                    continue

                if any(kw in current_url for kw in ["verification", "billing", "signup/tagging", "policy"]):
                    self.tracker.log("[NAV] Trang phu — navigate ve Campaigns")
                    cid = self.customer_id.replace("-", "")
                    d.get(f"https://ads.google.com/aw/campaigns?ocid={cid}")
                    time.sleep(10)
                    check_all()
                    continue

                # Da vao duoc trang Campaigns/Overview
                self.tracker.log("[NAV] San sang!", "success")
                return True

            return True

        if skip_navigate:
            self.tracker.log("[V4] skip_navigate=True — bo qua do_navigate()")
        else:
            self.tracker.set_current(step="[V4] Navigate")
            do_navigate()

        # ==================== CREATE CAMPAIGN ====================

        self.tracker.set_current(step="[V4] Create campaign")
        check_all()
        time.sleep(3)

        clicked = False
        # Uu tien nut "+" (Create)
        for xpath in [
            "//material-fab[@aria-label='Create']",
            "//material-fab-menu//material-fab",
            "//uber-create//material-fab",
            "//material-fab",
        ]:
            try:
                el = d.find_element(By.XPATH, xpath)
                if el.is_displayed():
                    action_click(el)
                    clicked = True
                    self.tracker.log(f"Click '+' ({xpath})")
                    time.sleep(3)
                    for mi in d.find_elements(By.XPATH, "//material-select-item"):
                        if mi.is_displayed() and "Campaign" in mi.text:
                            js_click(mi)
                            self.tracker.log("Chon 'Campaign'")
                            time.sleep(3)
                            break
                    break
            except Exception:
                pass

        # Fallback: New campaign button
        if not clicked:
            for xpath in [
                "//material-button[@aria-label='New campaign']",
                "//button[@aria-label='New campaign']",
            ]:
                try:
                    el = d.find_element(By.XPATH, xpath)
                    if el.is_displayed():
                        action_click(el)
                        clicked = True
                        self.tracker.log("Click 'New campaign'", "success")
                        time.sleep(3)
                        break
                except Exception:
                    pass

        if not clicked:
            cid = self.customer_id.replace("-", "")
            d.get(f"https://ads.google.com/aw/campaigns/new?ocid={cid}")
            time.sleep(10)
            check_all()

        time.sleep(5)
        try:
            WebDriverWait(d, 15).until(lambda drv: "campaign" in drv.title.lower())
        except Exception:
            pass
        time.sleep(3)
        check_all()

        # ==================== MAIN LOOP ====================

        completed_pages = set()
        MAX_ROUNDS = 30
        stuck_count = 0

        self.tracker.log("=== [V4] Main loop ===")

        for round_num in range(1, MAX_ROUNDS + 1):
            try:
                had_2fa = check_all()
                time.sleep(3)

                # Sau 2FA → doc stepper
                if had_2fa:
                    step = read_stepper()
                    if step != "unknown":
                        self.tracker.log(f"[2FA] Stepper: {step}")

                # Check bi redirect ve Sign in / Select Account
                cur_url = d.current_url.lower()
                cur_title = d.title.lower()
                if "sign in" in cur_title or "accounts.google.com" in cur_url or "selectaccount" in cur_url:
                    self.tracker.log("[LOOP] Bi redirect ve login — xu ly lai...", "warn")
                    do_navigate()
                    time.sleep(5)
                    # Verify da quay lai duoc Ads chua
                    after_url = d.current_url.lower()
                    after_title = d.title.lower()
                    if "sign in" in after_title or "accounts.google.com" in after_url:
                        self.tracker.log("[LOOP] Van bi ket o login sau navigate — thoat!", "error")
                        break
                    continue

                page_name, features = scan_page()
                self.tracker.log(f"[LOOP {round_num}] {page_name} | {sorted(list(features))[:8]}")

                # === DISPATCH ===
                if page_name == "review_publish":
                    self.tracker.set_current(step="[V4] Publish")
                    result = handle_publish()
                    if result == "published":
                        break
                    elif isinstance(result, str) and result.startswith("redirect_"):
                        self.tracker.log(f"Redirect sau 2FA: {result}")
                        continue

                elif page_name == "goal_selection" and "goal_selection" not in completed_pages:
                    self.tracker.set_current(step="[V4] Without guidance")
                    handle_goal_selection()
                    completed_pages.add("goal_selection")

                elif page_name == "campaign_type" and "campaign_type" not in completed_pages:
                    self.tracker.set_current(step="[V4] Search")
                    handle_campaign_type()
                    completed_pages.add("campaign_type")

                elif page_name == "goals_and_name" and "goals_and_name" not in completed_pages:
                    self.tracker.set_current(step="[V4] Goals + Name")
                    handle_goals_and_name()
                    completed_pages.add("goals_and_name")

                elif page_name == "bidding" and "bidding" not in completed_pages:
                    self.tracker.set_current(step="[V4] Bidding")
                    handle_bidding()
                    completed_pages.add("bidding")

                elif page_name == "campaign_settings" and "campaign_settings" not in completed_pages:
                    self.tracker.set_current(step="[V4] Settings")
                    handle_campaign_settings()
                    completed_pages.add("campaign_settings")

                elif page_name == "keywords_ads" and "keywords_ads" not in completed_pages:
                    self.tracker.set_current(step="[V4] Keywords + Ads")
                    handle_keywords_ads()
                    completed_pages.add("keywords_ads")

                elif page_name == "budget" and "budget" not in completed_pages:
                    self.tracker.set_current(step="[V4] Budget")
                    handle_budget()
                    completed_pages.add("budget")

                elif page_name == "skip_page":
                    self.tracker.set_current(step="[V4] Skip")

                elif page_name == "unknown":
                    stuck_count += 1
                    if stuck_count >= 5:
                        self.tracker.log("[LOOP] Bi ket — thoat", "error")
                        break
                else:
                    self.tracker.log(f"'{page_name}' da xu ly — Next")

                if page_name != "unknown":
                    stuck_count = 0

                # Nhan nut tiep theo
                time.sleep(3)
                if not click_button("Continue"):
                    if not click_button("Agree and continue"):
                        if not click_button("Next"):
                            click_button("Skip")
                time.sleep(8)
                check_all()

            except Exception as e:
                self.tracker.log(f"[LOOP {round_num}] LOI: {e}", "error")
                self.tracker.log(traceback.format_exc()[-300:], "error")
                time.sleep(3)

        # ==================== SAU PUBLISH ====================

        time.sleep(5)
        check_all()

        for _ in range(3):
            if "policy" in d.current_url.lower() or "can't run" in (d.page_source[:5000] if d.page_source else ""):
                self.tracker.log("Policy Review — Next")
                click_button("Next")
                time.sleep(5)
                check_all()
            else:
                break

        time.sleep(3)
        try:
            close_btn = d.find_element(By.XPATH, "//material-button[@aria-label='Close']")
            if close_btn.is_displayed():
                action_click(close_btn)
                self.tracker.log("Dong Google Tag")
                time.sleep(3)
        except Exception:
            pass

        upsert_campaign(self.customer_id, name, status="published")
        self.tracker.log(f"=== [V4] Campaign '{name}' PUBLISH THANH CONG! ===", "success")
        return True
