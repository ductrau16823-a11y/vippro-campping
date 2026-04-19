#!/usr/bin/env python3
"""
=== VIPPRO CAMPPING ===
Tao campaign Google Ads tu dong — scan trang truoc moi buoc, linh hoat xu ly.
Goi tu camp_runner.py sau khi da vao dung TK Ads.

Bai hoc thuc te (2026-04-15):
- Continue co the phai an 2 lan de hien checkbox + Campaign name
- Checkbox check bang icon text (check_box / check_box_outline_blank), KHONG dung class
- Bidding dropdown: click dropdown-button truoc, roi moi chon material-select-dropdown-item
- Budget: click radio Set custom budget + expand panel truoc khi dien
- 2FA: popup Confirm -> Try again -> tab moi Sign in -> nhap TOTP -> tab tu dong
- Popup: Conversion goals -> X, Exit guide -> Leave, Draft -> click ten hoac Start new
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
        self.driver = driver
        self.account_data = account_data
        self.tracker = tracker
        self.customer_id = account_data.get("accountId", "")
        self.gmail = account_data.get("gmailEmail", "")

    # STEP_ORDER dung cho start_step — moi step_id map 1 Buoc section.
    STEP_ORDER = [
        "navigate",      # Buoc 0
        "create",        # Buoc 4-5: Click Create > Campaign
        "setup",         # Buoc 6-13: Goal + Type + Website visits + Name + Page view
        "bidding",       # Buoc 14
        "settings",      # Buoc 15: Next + Networks
        "locations",     # Buoc 16
        "languages",     # Buoc 17
        "next_skip",     # Buoc 18-20
        "keywords_ads",  # Buoc 21
        "budget",        # Buoc 22
        "publish",       # Buoc 23 + post
    ]

    @staticmethod
    def detect_current_step(driver):
        """Auto-detect buoc hien tai dua tren URL + DOM elements.
        Return step_id trong STEP_ORDER, hoac 'done' neu da publish xong, hoac 'navigate' neu khong xac dinh.

        Thu tu check: tu buoc xa nhat (publish) lui dan — bat buoc xa nhat anh da di duoc.
        """
        from selenium.webdriver.common.by import By

        def has(xp):
            try:
                return any(e.is_displayed() for e in driver.find_elements(By.XPATH, xp))
            except Exception:
                return False

        try:
            cur_url = (driver.current_url or "").lower()
        except Exception:
            cur_url = ""
        try:
            cur_title = (driver.title or "").lower()
        except Exception:
            cur_title = ""

        # 1. Da publish xong — URL /campaigns khong kem /new
        if ("/campaigns" in cur_url and "/new" not in cur_url) or "signup/tagging" in cur_url:
            return "done"
        if "published" in cur_title:
            return "done"

        # 2. Review page (truoc publish)
        if has("//material-button[contains(., 'Publish campaign')] | //button[contains(., 'Publish campaign')]"):
            return "publish"

        # 3. Budget page
        if has("//material-radio[contains(., 'Set custom budget')] | "
               "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"):
            return "budget"

        # 4. Keywords/Ads page
        if has("//textarea[contains(@aria-label, 'keyword')] | "
               "//input[@aria-label='Final URL'] | "
               "//section[contains(@class, 'headline')]//input"):
            return "keywords_ads"

        # 5. Languages page (chip English hien ro)
        if has("//material-chip[contains(., 'English')] | "
               "//*[contains(normalize-space(.), 'Select the languages')]"):
            return "languages"

        # 6. Locations page
        if has("//*[contains(normalize-space(.), 'Enter another location')] | "
               "//material-radio[contains(., 'All countries and territories')]"):
            return "locations"

        # 7. Settings page (Networks)
        if has("//material-checkbox[contains(@class, 'search-checkbox')] | "
               "//material-checkbox[contains(@class, 'display-checkbox')] | "
               "//*[contains(normalize-space(.), 'Google Search Partners')] | "
               "//*[contains(normalize-space(.), 'Google Display Network')]"):
            return "settings"

        # 8. Bidding page
        if has("//material-dropdown-select//dropdown-button[contains(., 'Conversions') or contains(., 'Clicks') or contains(., 'Conversion value')] | "
               "//*[contains(normalize-space(.), 'Change bid strategy')] | "
               "//*[contains(normalize-space(.), 'What do you want to focus on')]"):
            return "bidding"

        # 9. Setup page (Campaign name / Website visits / Page view)
        if has("//input[@aria-label='Campaign name'] | "
               "//*[contains(normalize-space(.), 'Website visits')] | "
               "//*[contains(normalize-space(.), 'What results do you want')]"):
            return "setup"

        # 10. Create / Objective picker
        if ("/new" in cur_url) or has("//*[@data-value='No objective'] | "
                                       "//*[contains(normalize-space(.), 'Choose your objective')] | "
                                       "//*[contains(normalize-space(.), 'Start from scratch')]"):
            return "create"

        # 11. Da vao ads.google.com nhung chua bam Create
        if "ads.google.com" in cur_url:
            return "create"

        # Default: chay tu dau
        return "navigate"

    def run_campaign_flow(self, campaign_config, skip_navigate=False, camp_index=1, start_step=None):
        """Chay toan bo flow tao 1 campaign.

        Args:
            campaign_config: dict tu DB project
            skip_navigate: True neu camp_runner da vao san TK Ads
            camp_index: so thu tu camp tren TK nay (de danh so ten: viltrox 1, viltrox 2)
            start_step: neu set, bo qua cac Buoc truoc step nay (xem STEP_ORDER).
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.action_chains import ActionChains

        d = self.driver
        # B: Set Selenium timeout toan cuc — moi lenh sau 20s khong phan hoi -> TimeoutException
        # thay vi treo vo han (Chrome busy auto-save khien find_elements/is_displayed dang treo)
        try:
            d.set_script_timeout(20)
            d.set_page_load_timeout(30)
        except Exception as _te:
            self.tracker.log(f"[INIT] set_timeout fail: {_te}", "warn")
        base_name = campaign_config.get("name", "Campaign")
        name = f"{base_name} {camp_index}" if camp_index > 1 else base_name
        self.tracker.log(f"=== Bat dau tao campaign: {name} (#{camp_index}) ===")

        # Determine start index tu start_step
        _start_idx = 0
        _single_step = False  # Luon False: continue_camp chay tu start_step den het, khong skip
        if start_step:
            if start_step in CampaignCreator.STEP_ORDER:
                _start_idx = CampaignCreator.STEP_ORDER.index(start_step)
                self.tracker.log(f"[RESUME] start_step={start_step} — chay tu buoc nay den het", "warn")
            else:
                self.tracker.log(f"[RESUME] start_step='{start_step}' khong hop le — chay tu dau", "warn")

        def _run(step_id):
            """True khi step_id nam tu _start_idx tro di (khong skip cac buoc sau)."""
            try:
                idx = CampaignCreator.STEP_ORDER.index(step_id)
                return idx >= _start_idx
            except ValueError:
                return True

        def ads_url(path="/aw/campaigns"):
            """Build URL Google Ads dung __e (external account ID).
            __e on dinh + multi-account safe — Google tu resolve sang ocid noi bo."""
            cid = self.customer_id.replace("-", "")
            return f"https://ads.google.com{path}?__e={cid}"

        # State chia se giua cac helper closure
        nav_state = {
            "entered_ads": False,        # True khi da vao duoc TK Ads dashboard 1 lan
            "last_chooser_url": None,    # URL chooser lan truoc
            "chooser_clicks": 0,         # so lan click chooser cung 1 URL
            "last_select_url": None,     # URL selectaccount lan truoc
            "select_clicks": 0,          # so lan click selectaccount cung 1 URL
        }

        # ==================== HELPERS ====================

        def js_click(el):
            d.execute_script("arguments[0].click()", el)

        def action_click(el):
            ActionChains(d).move_to_element(el).pause(0.3).click().perform()

        def clear_and_type(el, value):
            """Click vao input, Ctrl+A roi type de — fix Material input."""
            el.click()
            time.sleep(0.3)
            el.send_keys(Keys.CONTROL, "a")
            time.sleep(0.2)
            el.send_keys(str(value))
            time.sleep(0.3)

        def js_set_textarea(el, value):
            """Dung JS set value cho textarea — fix send_keys nuot ky tu."""
            d.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                el, value,
            )

        def js_fill_input(el, value):
            """A: JS-fill cho input — KHONG trigger send_keys auto-save async (tranh treo sau fill CPC).
            Set .value qua native setter + dispatch input/change/blur de material binding cap nhat."""
            d.execute_script(
                "var el = arguments[0], v = String(arguments[1]);"
                "var proto = Object.getPrototypeOf(el);"
                "var setter = Object.getOwnPropertyDescriptor(proto, 'value') && Object.getOwnPropertyDescriptor(proto, 'value').set;"
                "if (setter) { setter.call(el, v); } else { el.value = v; }"
                "el.dispatchEvent(new Event('input', {bubbles: true}));"
                "el.dispatchEvent(new Event('change', {bubbles: true}));"
                "el.dispatchEvent(new Event('blur', {bubbles: true}));",
                el, value,
            )

        def click_button(text, timeout=10):
            """Tim va click button theo text chinh xac — 1 lan, khong retry."""
            enabled_match = None
            any_match = None
            for b in d.find_elements(By.XPATH, "//button | //material-button"):
                try:
                    if not b.is_displayed() or b.text.strip() != text:
                        continue
                    any_match = b
                    if b.get_attribute("aria-disabled") != "true" and b.is_enabled():
                        enabled_match = b
                        break
                except Exception:
                    pass
            target = enabled_match or any_match
            if target is None:
                return False
            try:
                action_click(target)
            except Exception as e:
                self.tracker.log(f"[click_button] '{text}' loi: {e}", "warn")
                return False
            time.sleep(1.5)
            try:
                if handle_2fa():
                    handle_popups()
            except Exception:
                pass
            return True

        def click_continue_or_agree():
            """Click 'Continue' hoac 'Agree and continue' — chon cai nao enabled + visible."""
            candidates = []
            for b in d.find_elements(By.XPATH, "//button | //material-button"):
                try:
                    if not b.is_displayed():
                        continue
                    t = b.text.strip()
                    if t in ("Continue", "Agree and continue"):
                        disabled = b.get_attribute("aria-disabled") == "true" or not b.is_enabled()
                        candidates.append((t, b, disabled))
                except Exception:
                    pass
            for t, b, disabled in candidates:
                if not disabled:
                    action_click(b)
                    self.tracker.log(f"Click '{t}'")
                    return True
            if candidates:
                action_click(candidates[0][1])
                self.tracker.log(f"Click '{candidates[0][0]}' (disabled fallback)")
                return True
            return False

        def click_by_text(text, exact=False):
            """Tim element bat ky chua text roi click — linh hoat cho card/radio/checkbox."""
            text_lc = text.lower()
            xpaths = [
                f"//*[normalize-space(text())='{text}']",
                f"//*[@role='radio' or @role='checkbox' or @role='button'][contains(., \"{text}\")]",
                f"//conversion-goal-card[.//*[contains(., \"{text}\")]]//button[@role='radio']",
                f"//conversion-goal-card[.//*[contains(., \"{text}\")]]",
                f"//mat-checkbox[contains(., \"{text}\")] | //material-checkbox[contains(., \"{text}\")]",
                f"//*[contains(normalize-space(.), \"{text}\")]",
            ]
            for xp in xpaths:
                try:
                    for el in d.find_elements(By.XPATH, xp):
                        try:
                            if not el.is_displayed():
                                continue
                            el_text = (el.text or "").strip()
                            if exact and el_text.lower() != text_lc:
                                continue
                            d.execute_script("arguments[0].scrollIntoView({block:'center', behavior:'smooth'})", el)
                            time.sleep(0.7)
                            try:
                                el.click()
                            except Exception:
                                js_click(el)
                            return True
                        except Exception:
                            continue
                except Exception:
                    continue
            return False

        def is_checkbox_ticked(cb_element):
            """Check checkbox dang tick hay chua — bang icon text."""
            return "check_box_outline_blank" not in cb_element.text

        def on_page(xpath):
            """Check xem trang co element match xpath + displayed hay khong."""
            try:
                return any(el.is_displayed() for el in d.find_elements(By.XPATH, xpath))
            except Exception:
                return False

        # ==================== PAGE DETECTOR + STEP VERIFIER ====================

        def detect_current_page():
            """Scan URL + key elements, return page name.
            Return: 'bidding' | 'settings' | 'locations' | 'languages' | 'ai_max'
                  | 'keyword_gen' | 'keywords_ads' | 'budget' | 'review'
                  | 'published' | '2fa' | 'unknown'
            """
            # 2FA dialog dang mo
            try:
                for dlg in d.find_elements(By.XPATH, "//material-dialog"):
                    if dlg.is_displayed() and "Confirm" in (dlg.text or ""):
                        return "2fa"
            except Exception:
                pass

            # Published URL sign — chi match khi KHONG con trong flow /aw/new
            try:
                cur_url = (d.current_url or "").lower()
                if "/campaigns" in cur_url and "/new" not in cur_url:
                    return "published"
                if "signup/tagging" in cur_url or "/policy" in cur_url:
                    return "published"
            except Exception:
                pass

            # Review page — co button "Publish campaign"
            try:
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    if b.is_displayed() and "Publish campaign" in (b.text or ""):
                        return "review"
            except Exception:
                pass

            # Bidding page — dropdown "What do you want to focus on?" or text "Maximize clicks"/"Change bid strategy"
            if on_page(
                "//material-dropdown-select//dropdown-button[contains(., 'Conversions') or contains(., 'Clicks') or contains(., 'Conversion value')] | "
                "//*[contains(normalize-space(.), 'Change bid strategy')] | "
                "//*[contains(normalize-space(.), 'What do you want to focus on')]"
            ):
                return "bidding"

            # Budget page
            if on_page(
                "//material-radio[contains(., 'Set custom budget')] | "
                "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"
            ):
                return "budget"

            # Campaign Settings page (consolidated: Networks + Locations + Languages)
            # QUAN TRONG: check truoc keywords_ads, ai_max, keyword_gen — vi cac trang do
            # khong co Networks checkbox nhung settings co the share mot vai xpath
            has_networks = on_page(
                "//material-checkbox[contains(@class, 'search-checkbox')] | "
                "//material-checkbox[contains(@class, 'display-checkbox')] | "
                "//*[contains(normalize-space(.), 'Google Search Partners')] | "
                "//*[contains(normalize-space(.), 'Google Display Network')]"
            )
            if has_networks:
                return "settings"
            has_locations = on_page(
                "//*[contains(normalize-space(.), 'Enter another location')] | "
                "//material-radio[contains(., 'All countries and territories')]"
            )
            if has_locations:
                return "locations"
            has_languages = on_page(
                "//material-chip[contains(., 'English')] | "
                "//*[contains(normalize-space(.), 'Select the languages')]"
            )
            if has_languages:
                return "languages"

            # AI Max for Search campaigns — trang skip (heading-based)
            if on_page(
                "//*[contains(normalize-space(.), 'AI Max for Search')] | "
                "//h1[contains(normalize-space(.), 'AI Max')] | "
                "//h2[contains(normalize-space(.), 'AI Max')]"
            ):
                return "ai_max"

            # Keyword and asset generation — trang skip (co nut 'Skip')
            if on_page(
                "//*[contains(normalize-space(.), 'Keyword and asset generation')] | "
                "//*[contains(normalize-space(.), 'keyword and asset')]"
            ):
                return "keyword_gen"

            # Keywords/Ads page — check sau ai_max/keyword_gen de tranh false positive
            if on_page(
                "//textarea[contains(@aria-label, 'keyword')] | "
                "//input[@aria-label='Final URL'] | "
                "//section[contains(@class, 'headline')]//input"
            ):
                return "keywords_ads"

            return "unknown"

        def verify_step(step_id, campaign_config=None):
            """Verify step da lam xong chua. Return (ok: bool, reason: str)."""
            cfg = campaign_config or {}
            try:
                if step_id == "navigate":
                    cur_url = (d.current_url or "").lower()
                    if "ads.google.com" in cur_url:
                        return True, "navigate OK"
                    return False, f"URL sai: {cur_url[:80]}"

                if step_id == "create":
                    # Da vao trang New campaign
                    if "new" in (d.current_url or "").lower() or "New campaign" in (d.title or ""):
                        return True, "create OK"
                    # Hoac tim thay card objective
                    if on_page("//*[@data-value='No objective'] | //*[contains(normalize-space(.), 'objective')]"):
                        return True, "create OK (objective card)"
                    return False, "chua vao trang New campaign"

                if step_id == "setup":
                    # Campaign name da dien + Page view da tick
                    name = cfg.get("name", "")
                    if name:
                        name_ok = False
                        for inp in d.find_elements(By.XPATH, "//input[@aria-label='Campaign name']"):
                            try:
                                if inp.is_displayed():
                                    val = (inp.get_attribute("value") or "").strip()
                                    if val:
                                        name_ok = True
                                        break
                            except Exception:
                                pass
                        # Neu da qua trang setup -> khong tim thay input -> coi nhu qua
                        if not name_ok and on_page("//input[@aria-label='Campaign name']"):
                            return False, "Campaign name rong"
                    return True, "setup OK (or passed)"

                if step_id == "bidding":
                    # Dropdown hien "Clicks" (neu expected)
                    bidding = (cfg.get("bidding") or "").lower()
                    cpc = cfg.get("cpc", "")
                    if "click" in bidding:
                        # Tim dropdown-button co text "Clicks"
                        found_clicks = False
                        for db in d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"):
                            try:
                                if db.is_displayed() and "Clicks" in (db.text or ""):
                                    found_clicks = True
                                    break
                            except Exception:
                                pass
                        # Page cung co the o text view 'Maximize clicks' (sau khi da chon Clicks)
                        if not found_clicks:
                            page_txt = (d.page_source[:20000] or "").lower()
                            if "maximize clicks" in page_txt:
                                found_clicks = True
                        if not found_clicks:
                            return False, "dropdown Clicks chua set"
                    # CPC input (neu co)
                    if cpc:
                        cpc_ok = False
                        for inp in d.find_elements(By.XPATH, "//input[@type='text' or @type='number']"):
                            try:
                                if inp.is_displayed():
                                    val = (inp.get_attribute("value") or "").strip()
                                    if val and (val == str(cpc) or val.replace("$", "").strip() == str(cpc).strip()):
                                        cpc_ok = True
                                        break
                            except Exception:
                                pass
                        if not cpc_ok:
                            return False, f"CPC chua dien = {cpc}"
                    return True, "bidding OK"

                if step_id == "settings":
                    # Ca 2 checkbox Network phai unchecked
                    for cls_name, label in [("search-checkbox", "Search Partners"), ("display-checkbox", "Display Network")]:
                        for c in d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls_name}')]"):
                            try:
                                if c.is_displayed() and is_checkbox_ticked(c):
                                    return False, f"{label} van tick"
                            except Exception:
                                pass
                    return True, "settings OK"

                if step_id == "locations":
                    target_locs = cfg.get("target_locations") or []
                    if not target_locs:
                        return True, "locations skip (no target)"
                    # Co chip Targeted hoac text "Targeted:"
                    if on_page("//*[contains(normalize-space(.), 'Targeted:')] | //material-chip[contains(., 'Targeted')]"):
                        return True, "locations OK"
                    return False, "chua co target locations"

                if step_id == "languages":
                    # Khong con chip "English"
                    for chip in d.find_elements(By.XPATH, "//material-chip[contains(., 'English')]"):
                        try:
                            if chip.is_displayed():
                                return False, "English chip van con"
                        except Exception:
                            pass
                    return True, "languages OK"

                if step_id == "keywords_ads":
                    # Final URL co value
                    final_url = cfg.get("final_url", "")
                    if final_url:
                        url_ok = False
                        for inp in d.find_elements(By.XPATH, "//input[@aria-label='Final URL']"):
                            try:
                                if inp.is_displayed():
                                    val = (inp.get_attribute("value") or "").strip()
                                    if val:
                                        url_ok = True
                                        break
                            except Exception:
                                pass
                        if not url_ok:
                            return False, "Final URL rong"
                    # It nhat 1 headline co text
                    headlines = cfg.get("headlines") or []
                    if headlines:
                        hl_count = 0
                        for inp in d.find_elements(By.XPATH, '//section[contains(@class, "headline")]//input'):
                            try:
                                if inp.is_displayed() and (inp.get_attribute("value") or "").strip():
                                    hl_count += 1
                            except Exception:
                                pass
                        if hl_count < 3:
                            return False, f"headlines chi co {hl_count}/{len(headlines)}"
                    return True, "keywords_ads OK"

                if step_id == "next_skip":
                    # Sau Next/Skip phai den duoc trang keywords_ads hoac xa hon
                    page = detect_current_page()
                    if page in ("keywords_ads", "budget", "review", "published"):
                        return True, f"next_skip OK (page={page})"
                    return False, f"Van ket o page={page}"

                if step_id == "budget":
                    budget = cfg.get("budget", "")
                    if not budget:
                        return True, "budget skip (no value)"
                    for inp in d.find_elements(By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"):
                        try:
                            if inp.is_displayed():
                                val = (inp.get_attribute("value") or "").strip()
                                if val and (val == str(budget) or val.replace(",", "").replace(".00", "") == str(budget)):
                                    return True, f"budget OK ({val})"
                        except Exception:
                            pass
                    return False, f"budget chua dien = {budget}"

                if step_id == "publish":
                    cur_url = (d.current_url or "").lower()
                    cur_title = (d.title or "").lower()
                    if "/campaigns" in cur_url and "/new" not in cur_url:
                        return True, "publish OK (URL /campaigns)"
                    if "published" in cur_title or "signup/tagging" in cur_url or "policy" in cur_url:
                        return True, "publish OK (title/URL)"
                    # Neu van o Review -> chua publish
                    if detect_current_page() == "review":
                        return False, "van o Review — chua publish"
                    return True, "publish (unknown — assume OK)"

                return True, f"no verify rule for '{step_id}'"
            except Exception as e:
                return True, f"verify error (ignore): {e}"

        # Map step -> page expected sau khi step xong (de phan tich auto-advance/regression)
        STEP_ORDER = ["navigate", "create", "setup", "bidding", "settings",
                      "locations", "languages", "next_skip", "keywords_ads", "budget", "publish"]
        PAGE_TO_STEP = {
            "bidding": "bidding",
            "settings": "settings",
            "locations": "locations",
            "languages": "languages",
            "keywords_ads": "keywords_ads",
            "budget": "budget",
            "review": "publish",
            "published": "publish",
        }

        def run_verify(step_id):
            """Log page hien tai, luon tra True — khong block flow."""
            try:
                page = detect_current_page()
                self.tracker.log(f"[VERIFY {step_id}] page={page}", "info")
            except Exception:
                pass
            return True

        # ==================== 2FA + POPUPS ====================

        def _solve_one_2fa():
            """Xu ly 1 popup Confirm + 2FA. Return True neu da xu ly 1 dialog, False neu khong co."""
            import pyotp
            import requests

            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or "Confirm" not in dialog.text:
                        continue
                except Exception:
                    continue
                except Exception:
                    continue

                self.tracker.log("[2FA] Gap popup xac thuc...", "warn")

                # Click Confirm hoac Try again
                for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                    try:
                        if b.is_displayed() and b.text.strip() in ("Confirm", "Try again"):
                            action_click(b)
                            self.tracker.log(f"[2FA] Click {b.text.strip()}")
                            time.sleep(5)
                            break
                    except Exception:
                        pass

                # Try again lan 2
                for d2 in d.find_elements(By.XPATH, "//material-dialog"):
                    try:
                        if d2.is_displayed() and "Try again" in d2.text:
                            for b2 in d2.find_elements(By.XPATH, ".//material-button | .//button"):
                                if b2.is_displayed() and "Try again" in b2.text:
                                    action_click(b2)
                                    self.tracker.log("[2FA] Click Try again")
                                    time.sleep(5)
                                    break
                            break
                    except Exception:
                        pass

                # Check tab 2FA moi
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

                            # Lay email tren trang
                            email = ""
                            for e in d.find_elements(By.XPATH, "//*[contains(text(), '@gmail.com')]"):
                                if e.is_displayed():
                                    email = e.text.strip().lower()
                                    break

                            # Lay 2FA key tu dashboard API
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
                                self.tracker.log("[2FA] OK!")
                                time.sleep(5)
                            break
                        except Exception:
                            pass

                    # Quay ve tab Ads
                    for h in d.window_handles:
                        d.switch_to.window(h)
                        try:
                            if "Google Ads" in d.title:
                                break
                        except Exception:
                            pass
                return True
            return False

        def handle_2fa():
            """Xu ly 1 lan 2FA neu co dialog."""
            return _solve_one_2fa()

        def handle_popups():
            """Dong popup Conversion goals / Exit guide."""
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or not dialog.text.strip():
                        continue
                    if "Conversion goals" in dialog.text:
                        for cb in dialog.find_elements(By.XPATH, ".//material-button[contains(@aria-label, 'Close')]"):
                            if cb.is_displayed():
                                js_click(cb)
                                self.tracker.log("[POPUP] Dong Conversion goals")
                                time.sleep(2)
                                break
                    elif "Exit guide" in dialog.text:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and "Leave" in b.text:
                                js_click(b)
                                self.tracker.log("[POPUP] Leave")
                                time.sleep(3)
                                break
                    elif "Fix errors" in dialog.text and "Discard" in dialog.text:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and b.text.strip() == "Fix errors":
                                action_click(b)
                                self.tracker.log("[POPUP] Fix errors — quay lai sua loi")
                                time.sleep(5)
                                break
                except Exception:
                    pass

        def handle_draft():
            """Xu ly dialog draft — click ten neu trung, Start new neu khac."""
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
            """Check 2FA + popup + draft truoc moi buoc."""
            had_2fa = handle_2fa()
            handle_popups()
            handle_draft()
            if had_2fa:
                # Sau 2FA — Google co the reset trang. Log URL + title de biet dang o dau.
                time.sleep(5)
                handle_popups()
                handle_draft()
                try:
                    self.tracker.log(
                        f"[2FA-DONE] Dang o: {d.current_url[:120]} | title: {(d.title or '')[:80]}",
                        "success"
                    )
                except Exception:
                    pass

        def check_login():
            """Check bi redirect ve login.
            - Neu CHUA tung vao ads -> goi do_navigate() day du.
            - Neu DA vao ads roi (entered_ads=True) -> chi cho transient redirect (KHONG re-select TK)."""
            cur_url = d.current_url.lower()
            cur_title = d.title.lower()
            on_login = "sign in" in cur_title or "accounts.google.com" in cur_url or "selectaccount" in cur_url
            if not on_login:
                return False

            if nav_state["entered_ads"]:
                # Da vao TK Ads thanh cong roi — co the la transient redirect, doi 8s xem co tu khoi phuc
                self.tracker.log("[CHECK] Phat hien chooser/login sau khi da vao Ads — cho transient...", "warn")
                for _ in range(4):
                    time.sleep(2)
                    new_url = d.current_url.lower()
                    if "ads.google.com" in new_url and "selectaccount" not in new_url and "accounts.google.com" not in new_url:
                        self.tracker.log("[CHECK] Da tu hoi phuc, khong can re-navigate", "success")
                        return True
                # Van bi kep — log error nhung KHONG re-select TK (tranh loop)
                self.tracker.log("[CHECK] Khong tu hoi phuc — abort, KHONG re-select TK", "error")
                return True

            # Chua vao ads bao gio -> do_navigate day du
            self.tracker.log("[CHECK] Bi redirect ve login (chua vao ads) — do_navigate()...", "warn")
            do_navigate()
            time.sleep(3)
            if "ads.google.com" not in d.current_url.lower() or "campaign" not in d.title.lower():
                d.get(ads_url("/aw/campaigns/new"))
                time.sleep(10)
                check_all()
            return True

        def do_navigate():
            """Xu ly full login: Account Chooser, email, password, 2FA, Select Account."""
            from camp_runner import get_gmail_password, get_2fa_key, generate_totp
            profile_id = self.account_data.get("profileId", "")
            gmail_email = self.gmail

            for nav_try in range(5):
                cur_url = d.current_url.lower()
                cur_title = d.title.lower()
                self.tracker.log(f"[NAV] Trang: {d.title} (lan {nav_try + 1})")

                # Account Chooser
                try:
                    heading = d.find_element(By.CSS_SELECTOR, "h1#headingText span")
                    if "Choose an account" in heading.text or "Chọn tài khoản" in heading.text:
                        # Loop detection: cung URL chooser xuat hien lan thu 3 -> abort
                        if nav_state["last_chooser_url"] == cur_url:
                            nav_state["chooser_clicks"] += 1
                            if nav_state["chooser_clicks"] >= 2:
                                self.tracker.log(
                                    f"[NAV] LOOP tren Account Chooser ({nav_state['chooser_clicks']+1}x cung URL) — abort do_navigate",
                                    "error",
                                )
                                return False
                        else:
                            nav_state["chooser_clicks"] = 0
                            nav_state["last_chooser_url"] = cur_url

                        self.tracker.log("[NAV] Account Chooser...")
                        try:
                            el = WebDriverWait(d, 8).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, f'div[data-identifier="{gmail_email.lower()}"]'))
                            )
                            action_click(el)
                            self.tracker.log(f"[NAV] Click {gmail_email}")
                            time.sleep(5)
                        except Exception:
                            for el in d.find_elements(By.XPATH, "//div[@data-identifier]"):
                                if el.is_displayed():
                                    action_click(el)
                                    time.sleep(5)
                                    break
                        continue
                except Exception:
                    pass

                if "sign in" in cur_title or "accounts.google.com" in cur_url:
                    # Email input
                    try:
                        email_input = d.find_element(By.CSS_SELECTOR, "input[type='email']#identifierId")
                        if email_input.is_displayed():
                            email_input.clear()
                            email_input.send_keys(gmail_email)
                            time.sleep(0.5)
                            try:
                                d.find_element(By.CSS_SELECTOR, "#identifierNext button").click()
                                self.tracker.log(f"[NAV] Nhap email: {gmail_email}")
                                time.sleep(4)
                            except Exception:
                                pass
                            continue
                    except Exception:
                        pass
                    # Password
                    try:
                        pw_input = d.find_element(By.CSS_SELECTOR, "input[type='password'][name='Passwd']")
                        if pw_input.is_displayed():
                            password = get_gmail_password(profile_id) if profile_id else None
                            if password:
                                pw_input.clear()
                                pw_input.send_keys(password)
                                time.sleep(0.5)
                                try:
                                    d.find_element(By.CSS_SELECTOR, "#passwordNext button").click()
                                    self.tracker.log("[NAV] Nhap password", "success")
                                    time.sleep(5)
                                except Exception:
                                    pass
                            continue
                    except Exception:
                        pass
                    # 2FA
                    try:
                        totp_input = d.find_element(By.CSS_SELECTOR, "input#totpPin")
                        if totp_input.is_displayed():
                            secret = get_2fa_key(profile_id) if profile_id else None
                            if secret:
                                code = generate_totp(secret)
                                totp_input.click()
                                time.sleep(0.3)
                                totp_input.send_keys(code)
                                time.sleep(1)
                                try:
                                    d.find_element(By.CSS_SELECTOR, "#totpNext button").click()
                                    self.tracker.log(f"[NAV] Nhap 2FA: {code}", "success")
                                    time.sleep(5)
                                except Exception:
                                    pass
                            continue
                    except Exception:
                        pass
                    # Fallback: click data-identifier
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
                    continue

                if "selectaccount" in cur_url:
                    # Loop detection: cung URL selectaccount lan thu 3 -> abort
                    if nav_state["last_select_url"] == cur_url:
                        nav_state["select_clicks"] += 1
                        if nav_state["select_clicks"] >= 2:
                            self.tracker.log(
                                f"[NAV] LOOP tren Select Account ({nav_state['select_clicks']+1}x cung URL) — abort",
                                "error",
                            )
                            return False
                    else:
                        nav_state["select_clicks"] = 0
                        nav_state["last_select_url"] = cur_url

                    self.tracker.log("[NAV] Select Account...")
                    for item in d.find_elements(By.CSS_SELECTOR, "material-list-item"):
                        if self.customer_id in item.text and "Setup in progress" not in item.text:
                            item.click()
                            self.tracker.log(f"[NAV] Chon TK {self.customer_id}")
                            time.sleep(10)
                            break
                    continue

                if any(kw in cur_url for kw in ["verification", "billing", "signup/tagging", "policy"]):
                    self.tracker.log("[NAV] Trang phu — navigate ve Campaigns")
                    d.get(ads_url("/aw/campaigns"))
                    time.sleep(10)
                    check_all()
                    continue

                # Da o trang ads.google.com (khong phai login/selectaccount/sub-page)
                if "ads.google.com" in cur_url:
                    nav_state["entered_ads"] = True
                self.tracker.log("[NAV] San sang!", "success")
                return True
            return True

        # ==================== MAIN FLOW ====================

        # === BUOC 0: Navigate ===
        while _run("navigate"):
            self.tracker.set_current(step="Buoc 0: Navigate")
            time.sleep(1.2)  # buffer cho DOM on dinh
            self.tracker.log(f"Trang hien tai: {d.title}")

            if skip_navigate:
                cur_url = d.current_url.lower()
                cur_title = d.title.lower()
                if "sign in" in cur_title or "accounts.google.com" in cur_url or "selectaccount" in cur_url:
                    self.tracker.log("[NAV] skip_navigate=True nhung dang o login — do_navigate()", "warn")
                    do_navigate()
                else:
                    self.tracker.log("[NAV] Da o trang Ads", "success")
                    nav_state["entered_ads"] = True
            else:
                do_navigate()

            # Sau navigate: neu URL dang o ads.google.com -> mark entered
            if "ads.google.com" in d.current_url.lower() and "selectaccount" not in d.current_url.lower():
                nav_state["entered_ads"] = True

            # Check TK suspended — KHONG len camp neu bi suspend
            try:
                from camp_runner import check_account_status
                profile_name = self.account_data.get("profileName") or ""
                account_db_id = self.account_data.get("id")
                tk_status = check_account_status(d, profile_name, self.customer_id, account_db_id)
                if tk_status == "suspended":
                    self.tracker.log(f"TK {self.customer_id} BI SUSPENDED — skip!", "error")
                    return False
            except Exception as e:
                self.tracker.log(f"[WARN] check_account_status loi: {e}", "warn")
            run_verify("navigate")
            break
        else:
            self.tracker.log("[SKIP] Buoc 0: Navigate (start_step)", "warn")
            # Khi resume: gia dinh da vao Ads roi
            nav_state["entered_ads"] = True

        # === BUOC 4-5: Click Create > Campaign ===
        while _run("create"):
            self.tracker.set_current(step="Buoc 4-5: Create > Campaign")
            time.sleep(1.2)  # buffer cho DOM on dinh
            check_all()
            time.sleep(3)

            # Thu nhieu cach tim nut Create / New campaign
            clicked = False
            for xpath in [
                "//material-button[@aria-label='New campaign']",
                "//button[@aria-label='New campaign']",
                "//material-fab-menu//material-fab",
                "//uber-create//material-fab",
                "//material-fab",
            ]:
                try:
                    el = d.find_element(By.XPATH, xpath)
                    if el.is_displayed():
                        action_click(el)
                        clicked = True
                        self.tracker.log(f"Click {xpath}")
                        time.sleep(3)
                        # Neu la fab, can chon Campaign trong menu
                        if "fab" in xpath:
                            for mi in d.find_elements(By.XPATH, "//material-select-item"):
                                if mi.is_displayed() and "Campaign" in mi.text:
                                    js_click(mi)
                                    time.sleep(3)
                                    break
                        break
                except Exception:
                    pass

            if not clicked:
                self.tracker.log("Khong tim thay nut Create — thu navigate truc tiep", "warn")
                d.get(ads_url("/aw/campaigns/new"))
                time.sleep(10)
                check_all()
                clicked = True

            if not clicked:
                self.tracker.log("Khong tim thay nut Create!", "error")
                return False

            time.sleep(5)
            self.tracker.log("Da click Create > Campaign", "success")

            # Doi trang New campaign load
            try:
                WebDriverWait(d, 15).until(lambda drv: "campaign" in drv.title.lower())
            except Exception:
                pass
            time.sleep(3)
            check_all()
            run_verify("create")
            break
        else:
            self.tracker.log("[SKIP] Buoc 4-5: Create > Campaign (start_step)", "warn")

        # === BUOC 6-13: Setup campaign — thu tung action truc tiep, khong scan ===
        while _run("setup"):
            self.tracker.set_current(step="Buoc 6-13: Setup campaign")
            time.sleep(1.2)  # buffer cho DOM on dinh
            time.sleep(3)

            camp_type = campaign_config.get("type", "search").upper()
            done_objective = False
            done_type = False
            done_visits = False
            done_pv = False
            done_name = False

            PV_XPATHS = [
                "//conversion-goal-card[.//*[@id='PAGE_VIEW']]",
                "//conversion-goal-card[.//material-icon[@id='PAGE_VIEW']]//button[@role='radio']",
                "//button[@role='radio'][.//material-icon[@id='PAGE_VIEW']]",
                "//conversion-goal-picker//material-radio[.//*[contains(normalize-space(.), 'Page view')]]",
                "//material-radio[.//*[contains(normalize-space(.), 'Page view')]]",
                "//button[@role='radio'][.//div[contains(@class, 'title') and contains(text(), 'Page view')]]",
                "//conversion-goal-card[.//div[contains(@class, 'title') and contains(text(), 'Page view')]]//button",
                "//conversion-goal-card[.//div[contains(text(), 'Page view')]]//button",
                "//conversion-goal-card[.//div[contains(text(), 'Page view')]]",
            ]

            for attempt in range(8):
                check_all()
                check_login()
                self.tracker.log(f"[#{attempt+1}] obj={done_objective} type={done_type} visits={done_visits} pv={done_pv} name={done_name}")

                # --- Without guidance ---
                if not done_objective:
                    try:
                        el = d.find_element(By.XPATH, "//*[@data-value='No objective']")
                        if el.is_displayed():
                            js_click(el)
                            done_objective = True
                            self.tracker.log("Chon without guidance", "success")
                            time.sleep(0.5)
                    except Exception:
                        pass

                # --- Campaign type (Search) ---
                if not done_type:
                    try:
                        el = d.find_element(By.XPATH, f"//*[@data-value='{camp_type}']")
                        if el.is_displayed():
                            js_click(el)
                            done_type = True
                            self.tracker.log(f"Chon {camp_type}", "success")
                            time.sleep(0.5)
                    except Exception:
                        pass

                # --- Enhanced conversions: bo tick (TK moi chua co camp) ---
                for cb in d.find_elements(By.XPATH,
                        "//enhanced-conversions-view//mat-checkbox | //material-checkbox | //mat-checkbox"):
                    try:
                        if not cb.is_displayed():
                            continue
                        if "enhanced conversions" not in cb.text.lower():
                            continue
                        if not is_checkbox_ticked(cb):
                            self.tracker.log("Enhanced conversions da bo tick san — skip")
                            break
                        # Thu Selenium native truoc de trigger material listener
                        try:
                            cb.click()
                        except Exception:
                            try:
                                action_click(cb)
                            except Exception:
                                js_click(cb)
                        time.sleep(0.7)
                        # Verify da bo tick
                        if not is_checkbox_ticked(cb):
                            self.tracker.log("Bo tick Enhanced conversions", "success")
                        else:
                            try:
                                js_click(cb)
                                time.sleep(0.5)
                            except Exception:
                                pass
                            if not is_checkbox_ticked(cb):
                                self.tracker.log("Bo tick Enhanced conversions (JS fallback)", "success")
                            else:
                                self.tracker.log("KHONG bo duoc tick Enhanced conversions", "warn")
                        break
                    except Exception:
                        pass

                # --- Website visits: tick ---
                if not done_visits:
                    for c in d.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
                        try:
                            if c.is_displayed() and "Website visits" in c.text:
                                if not is_checkbox_ticked(c):
                                    js_click(c)
                                    self.tracker.log("Tick Website visits", "success")
                                    time.sleep(0.5)
                                done_visits = True
                                break
                        except Exception:
                            pass

                # --- Campaign name ---
                if not done_name:
                    try:
                        name_input = d.find_element(By.XPATH, "//input[@aria-label='Campaign name']")
                        if name_input.is_displayed():
                            clear_and_type(name_input, name)
                            self.tracker.log(f"Dien Campaign name: {name}", "success")
                            done_name = True
                            time.sleep(0.3)
                    except Exception:
                        pass

                # --- Page view (copy tu v4: tick_on_row) ---
                if not done_pv:
                    pv_text = "Page view"
                    pv_esc = f'"{pv_text}"'
                    container_xpaths = (
                        f"//conversion-goal-card[.//*[normalize-space(text())={pv_esc}]]",
                        f"//tr[.//*[normalize-space(text())={pv_esc}]]",
                        f"//*[@role='row'][.//*[normalize-space(text())={pv_esc}]]",
                        f"//li[.//*[normalize-space(text())={pv_esc}]]",
                        f"//*[contains(@class,'row')][.//*[normalize-space(text())={pv_esc}]]",
                        f"//*[contains(@class,'card')][.//*[normalize-space(text())={pv_esc}]]",
                        f"//*[normalize-space(text())={pv_esc}]/ancestor::*[self::div or self::li or self::section][1]",
                    )
                    tick_xpaths = (
                        ".//*[@role='checkbox']",
                        ".//*[@role='radio']",
                        ".//material-checkbox",
                        ".//mat-checkbox",
                        ".//material-radio",
                        ".//mat-radio-button",
                        ".//button[@role='radio']",
                        ".//button[@role='checkbox']",
                        ".//input[@type='checkbox']",
                        ".//input[@type='radio']",
                    )
                    found_pv = False
                    for cxp in container_xpaths:
                        if found_pv:
                            break
                        for container in d.find_elements(By.XPATH, cxp):
                            if found_pv:
                                break
                            try:
                                if not container.is_displayed():
                                    continue
                            except Exception:
                                continue
                            for txp in tick_xpaths:
                                if found_pv:
                                    break
                                for el in container.find_elements(By.XPATH, txp):
                                    try:
                                        if not el.is_displayed():
                                            continue
                                        d.execute_script("arguments[0].scrollIntoView({block:'center', behavior:'smooth'})", el)
                                        time.sleep(0.7)
                                        try:
                                            el.click()
                                        except Exception:
                                            js_click(el)
                                        done_pv = True
                                        found_pv = True
                                        self.tracker.log("Tick Page view (row)", "success")
                                        time.sleep(0.3)
                                        break
                                    except Exception:
                                        pass
                    # Fallback PV_XPATHS cu neu tick_on_row fail
                    if not done_pv:
                        for xp in PV_XPATHS:
                            if done_pv:
                                break
                            for el in d.find_elements(By.XPATH, xp):
                                try:
                                    if not el.is_displayed():
                                        continue
                                    d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", el)
                                    time.sleep(0.7)
                                    js_click(el)
                                    done_pv = True
                                    self.tracker.log("Click Page view (xpath)", "success")
                                    time.sleep(0.3)
                                    break
                                except Exception:
                                    pass

                # --- Xong? ---
                if done_name and (done_pv or attempt >= 4):
                    self.tracker.log(f"Xong! obj={done_objective} type={done_type} visits={done_visits} pv={done_pv} name={done_name}")
                    click_continue_or_agree()
                    time.sleep(5)
                    check_all()
                    check_login()
                    break

                # Chua xong → Continue de chuyen trang / hien form tiep
                self.tracker.log("Continue...")
                click_continue_or_agree()
                time.sleep(5)
                check_all()
                check_login()
            run_verify("setup")
            break
        else:
            self.tracker.log("[SKIP] Buoc 6-13: Setup campaign (start_step)", "warn")

        # === BUOC 14: Bidding ===
        while _run("bidding"):
            self.tracker.set_current(step="Buoc 14: Bidding")
            time.sleep(1.2)  # buffer cho DOM on dinh
            self.tracker.log(">>> VAO BUOC 14: Bidding")
            check_all()
            time.sleep(3)
            bidding = campaign_config.get("bidding", "maximize_clicks")
            cpc = campaign_config.get("cpc", "")
            self.tracker.log(f"[14] bidding='{bidding}' cpc='{cpc}'")

            # Scan trang thai hien tai truoc khi lam
            page_txt_lower = (d.page_source[:30000] or "").lower()
            has_change_link = "change bid strategy" in page_txt_lower
            dropdown_els = d.find_elements(
                By.XPATH,
                "//material-dropdown-select//dropdown-button[contains(., 'Conversions') or contains(., 'Clicks') or contains(., 'Conversion value')]"
            )
            has_dropdown = any(e.is_displayed() for e in dropdown_els if e)
            self.tracker.log(f"[14] state: has_change_link={has_change_link} has_dropdown={has_dropdown}")

            # === PRE-CHECK: Neu UI da dung (Clicks + CPC dung) -> skip actions, click Next luon ===
            # Tranh trigger auto-save khi state da OK tu draft truoc.
            bidding_already_ok = False
            try:
                dropdown_txt = ""
                for db in dropdown_els:
                    try:
                        if db.is_displayed():
                            dropdown_txt = (db.text or "").strip()
                            break
                    except Exception:
                        pass
                cpc_already_ok = True
                if cpc:
                    cpc_already_ok = False
                    for inp in d.find_elements(By.XPATH, "//input[@type='text' or @type='number']"):
                        try:
                            if inp.is_displayed():
                                cur_val = (inp.get_attribute("value") or "").strip().replace("$", "").strip()
                                if cur_val == str(cpc).strip():
                                    cpc_already_ok = True
                                    break
                        except Exception:
                            pass
                dropdown_ok = ("click" not in bidding.lower()) or ("Clicks" in dropdown_txt)
                if dropdown_ok and cpc_already_ok:
                    bidding_already_ok = True
                    self.tracker.log(f"[14] PRE-CHECK: UI DA DUNG (dropdown='{dropdown_txt[:20]}' cpc_ok={cpc_already_ok}) — skip actions", "success")
            except Exception as _e:
                self.tracker.log(f"[14] PRE-CHECK loi: {_e}", "warn")

            if bidding_already_ok:
                # Skip toan bo dropdown/tick/fill — chi click Next
                self.tracker.log("[14] Skip actions, click Next luon", "info")
                click_button("Next")
                time.sleep(4)
                check_all()
                run_verify("bidding")
                break

            if "click" in bidding.lower():
                # Neu trang dang o che do text "Maximize clicks" (khong co dropdown) + co link Change bid strategy
                # -> BAT BUOC click Change bid strategy de chuyen ve form 'What do you want to focus on?' co dropdown
                try:
                    if has_change_link:
                        self.tracker.log("[14] Phat hien 'Change bid strategy' — click de mo form (B: luon click neu co link)")
                        change_xpaths = [
                            "//a[contains(normalize-space(.), 'Change bid strategy')]",
                            "//*[@role='link'][contains(normalize-space(.), 'Change bid strategy')]",
                            "//button[contains(normalize-space(.), 'Change bid strategy')]",
                            "//span[contains(normalize-space(.), 'Change bid strategy')]/ancestor::a",
                            "//span[contains(normalize-space(.), 'Change bid strategy')]/ancestor::button",
                            "//*[contains(normalize-space(.), 'Change bid strategy')][self::a or self::button or @role='link' or @role='button']",
                            "//*[contains(normalize-space(text()), 'Change bid strategy')]",
                        ]
                        changed = False
                        for xp in change_xpaths:
                            try:
                                els = d.find_elements(By.XPATH, xp)
                                self.tracker.log(f"[14] xp '{xp[:55]}' -> {len(els)} el")
                                for el in els:
                                    try:
                                        # Scroll vao view TRUOC khi check displayed
                                        try:
                                            d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", el)
                                        except Exception:
                                            pass
                                        time.sleep(0.7)
                                        is_vis = el.is_displayed()
                                        el_text = (el.text or "")[:80]
                                        self.tracker.log(f"[14]   el text='{el_text}' vis={is_vis}")
                                        # Thu click du is_displayed hay khong (mot so link bi CSS an nhung van click duoc qua JS)
                                        for click_method in ("action", "js"):
                                            try:
                                                if click_method == "action":
                                                    action_click(el)
                                                else:
                                                    d.execute_script("arguments[0].click()", el)
                                                self.tracker.log(f"[14] Da click 'Change bid strategy' ({click_method})", "success")
                                                changed = True
                                                time.sleep(1.5)
                                                break
                                            except Exception as ce:
                                                self.tracker.log(f"[14]   click {click_method} fail: {ce}", "warn")
                                        if changed:
                                            break
                                    except Exception as ee:
                                        self.tracker.log(f"[14]   loi check el: {ee}", "warn")
                                if changed:
                                    break
                            except Exception as xe:
                                self.tracker.log(f"[14] loi xpath: {xe}", "warn")
                        if not changed:
                            self.tracker.log("[14] Khong click duoc 'Change bid strategy'", "error")
                        else:
                            # Sau khi click Change bid strategy — re-check dropdown
                            time.sleep(1)
                            new_dd = d.find_elements(
                                By.XPATH,
                                "//material-dropdown-select//dropdown-button[contains(., 'Conversions') or contains(., 'Clicks') or contains(., 'Conversion value')]"
                            )
                            self.tracker.log(f"[14] Sau click: dropdown={len(new_dd)} el")
                except Exception as e:
                    self.tracker.log(f"[14] Loi check 'Change bid strategy': {e}", "warn")

                # Mo dropdown bang dropdown-button (KHONG click text Conversions truc tiep)
                clicked_dropdown = False
                selectors = [
                    "//material-dropdown-select//dropdown-button",
                    "//dropdown-button[contains(., 'Conversions') or contains(., 'Clicks') or contains(., 'Conversion value')]",
                    "//*[@role='button'][contains(., 'Conversions') or contains(., 'Clicks')]",
                ]
                for xp in selectors:
                    try:
                        dbs = d.find_elements(By.XPATH, xp)
                        self.tracker.log(f"[14] Selector '{xp[:60]}' -> {len(dbs)} element")
                        for db in dbs:
                            try:
                                if not db.is_displayed():
                                    continue
                                txt = (db.text or "").strip()
                                self.tracker.log(f"[14] dropdown text: '{txt[:60]}'")
                                if "Conversions" in txt or "Clicks" in txt or "Conversion value" in txt:
                                    action_click(db)
                                    self.tracker.log("[14] Da click dropdown", "success")
                                    time.sleep(0.7)
                                    clicked_dropdown = True
                                    break
                            except Exception as e:
                                self.tracker.log(f"[14] Loi check dropdown: {e}", "warn")
                        if clicked_dropdown:
                            break
                    except Exception as e:
                        self.tracker.log(f"[14] Loi find dropdown: {e}", "warn")

                if not clicked_dropdown:
                    self.tracker.log("[14] KHONG tim thay dropdown bidding!", "error")

                # Chon Clicks — thu Selenium native click truoc, verify UI doi thanh 'Clicks'
                if clicked_dropdown:
                    picked = False
                    try:
                        items = d.find_elements(By.XPATH, "//material-select-dropdown-item | //*[@role='option']")
                        self.tracker.log(f"[14] Tim thay {len(items)} dropdown-item")
                        for item in items:
                            try:
                                if item.is_displayed() and item.text.strip() == "Clicks":
                                    # Try Selenium native (material cần real click để trigger listener)
                                    try:
                                        item.click()
                                    except Exception:
                                        try:
                                            action_click(item)
                                        except Exception:
                                            js_click(item)
                                    time.sleep(1.5)
                                    # Verify dropdown text da doi thanh 'Clicks'
                                    new_txt = ""
                                    try:
                                        for db in d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"):
                                            if db.is_displayed():
                                                new_txt = (db.text or "").strip()
                                                break
                                    except Exception:
                                        pass
                                    if "Clicks" in new_txt:
                                        self.tracker.log(f"[14] Da chon Clicks bidding (UI='{new_txt[:30]}')", "success")
                                        picked = True
                                        break
                                    else:
                                        self.tracker.log(f"[14] Click chua lam UI doi (UI='{new_txt[:30]}') — retry ActionChains", "warn")
                                        try:
                                            ActionChains(d).move_to_element(item).pause(0.3).click().perform()
                                            time.sleep(1.5)
                                        except Exception:
                                            pass
                                        for db in d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"):
                                            if db.is_displayed() and "Clicks" in (db.text or ""):
                                                self.tracker.log("[14] Da chon Clicks bidding (retry)", "success")
                                                picked = True
                                                break
                                        if picked:
                                            break
                            except Exception as e:
                                self.tracker.log(f"[14] Loi check item: {e}", "warn")
                        if not picked:
                            self.tracker.log("[14] KHONG chon duoc 'Clicks' (UI khong doi)!", "error")
                    except Exception as e:
                        self.tracker.log(f"[14] Loi list dropdown-item: {e}", "warn")

            # Tick checkbox max CPC + dien CPC (neu co) — tuyen tinh, KHONG nested thread.
            # wait_dom_idle da gay treo vi poll execute_script trong khi Selenium session bi
            # lock boi auto-save. Neu click Next bi treo -> throw -> camp_runner watchdog retry.
            if cpc:
                try:
                    ticked = False
                    checkboxes = d.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox")
                    self.tracker.log(f"[14] Tim thay {len(checkboxes)} checkbox")
                    for c in checkboxes:
                        try:
                            if c.is_displayed() and "maximum cost per click" in (c.text or "").lower():
                                already_ticked = False
                                try:
                                    aria_checked = (c.get_attribute("aria-checked") or "").lower()
                                    cls = (c.get_attribute("class") or "").lower()
                                    if aria_checked == "true" or "is-checked" in cls or "checked" in cls:
                                        already_ticked = True
                                except Exception:
                                    pass
                                if already_ticked:
                                    self.tracker.log("[14] Checkbox max CPC DA tick san — skip", "success")
                                else:
                                    # Selenium native click de trigger material listener
                                    try:
                                        c.click()
                                    except Exception:
                                        js_click(c)
                                    self.tracker.log("[14] Da tick checkbox max CPC", "success")
                                    time.sleep(1)
                                ticked = True
                                break
                        except Exception as e:
                            self.tracker.log(f"[14] Loi check checkbox CPC: {e}", "warn")
                    if not ticked:
                        self.tracker.log("[14] KHONG tim thay checkbox max CPC", "warn")
                except Exception as e:
                    self.tracker.log(f"[14] Loi tick CPC checkbox: {e}", "warn")

                # Dien CPC trong max-bid-container
                try:
                    filled = False
                    sections = d.find_elements(By.XPATH, "//div[contains(@class, 'max-bid-container')] | //section[.//span[contains(text(), 'Maximum CPC')]]")
                    self.tracker.log(f"[14] Tim thay {len(sections)} max-bid section")
                    for s in sections:
                        try:
                            if not s.is_displayed():
                                continue
                            for inp in s.find_elements(By.XPATH, ".//input"):
                                if inp.is_displayed():
                                    try:
                                        cur_val = (inp.get_attribute("value") or "").strip()
                                        if cur_val and (cur_val == cpc or cur_val.replace("$", "").strip() == str(cpc).strip()):
                                            self.tracker.log(f"[14] CPC da dien san ({cur_val}) — skip", "success")
                                            filled = True
                                            break
                                    except Exception:
                                        pass
                                    js_fill_input(inp, cpc)
                                    self.tracker.log(f"[14] Da dien CPC: {cpc} (JS-fill)", "success")
                                    filled = True
                                    break
                            if filled:
                                break
                        except Exception as e:
                            self.tracker.log(f"[14] Loi dien CPC section: {e}", "warn")
                    if not filled:
                        for inp in d.find_elements(By.XPATH, "//input[@type='text' or @type='number']"):
                            try:
                                if inp.is_displayed() and inp.is_enabled():
                                    parent_text = ""
                                    try:
                                        parent_text = inp.find_element(By.XPATH, "./ancestor::*[position()<=5]").text.lower()
                                    except Exception:
                                        pass
                                    if "cpc" in parent_text or "maximum" in parent_text:
                                        js_fill_input(inp, cpc)
                                        self.tracker.log(f"[14] Da dien CPC (fallback, JS-fill): {cpc}", "success")
                                        filled = True
                                        break
                            except Exception:
                                pass
                        if not filled:
                            self.tracker.log("[14] KHONG dien duoc CPC", "error")
                except Exception as e:
                    self.tracker.log(f"[14] Loi dien CPC: {e}", "warn")

            # Buffer 2s sau fill CPC cho material binding ngam gia tri, roi click Next.
            time.sleep(2)
            self.tracker.log("[14] Click Next de sang settings...", "info")
            # Bao click_button trong daemon thread timeout 20s — tranh hang
            # sau fill CPC (Chrome auto-save lam find_elements trong click_button treo).
            _next_done = {"flag": False}
            def _click_next_safe():
                try:
                    click_button("Next")
                    _next_done["flag"] = True
                except Exception as _ce:
                    self.tracker.log(f"[14] click Next exception: {_ce}", "warn")
            import threading as _t14b
            _thr = _t14b.Thread(target=_click_next_safe, daemon=True)
            _thr.start()
            _thr.join(timeout=20)
            if not _next_done["flag"]:
                self.tracker.log("[14] click Next TREO >20s — continue, camp_runner se retry neu can", "error")
            time.sleep(4)
            check_all()
            run_verify("bidding")
            break
        else:
            self.tracker.log("[SKIP] Buoc 14: Bidding (start_step)", "warn")

        # === BUOC 15: Campaign Settings (Networks) ===
        while _run("settings"):
            self.tracker.set_current(step="Buoc 15: Campaign Settings")
            self.tracker.log(">>> VAO BUOC 15: Campaign Settings", "info")
            time.sleep(1.2)  # buffer cho DOM on dinh
            check_all()
            time.sleep(2)  # Doi trang Settings render hoan toan

            # Bo tick Search Partners + Display Network — match theo text label
            # QUAN TRONG: Google auto-save sau moi click, phai doi save xong roi moi click tiep
            # neu khong se bi loi "Changes failed to save" va click sau bi mat
            NETWORK_LABELS = [
                ("search-checkbox", "Google Search Partners"),
                ("display-checkbox", "Google Display Network"),
            ]

            def find_network_cb(cls_name, label):
                """Tim lai checkbox moi lan — stale reference neu DOM reload."""
                # Thu 1: class cu
                for c in d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls_name}')]"):
                    try:
                        if c.is_displayed():
                            return c
                    except Exception:
                        pass
                # Thu 2: text label
                try:
                    cbs = d.find_elements(
                        By.XPATH,
                        f"//material-checkbox[ancestor::*[self::div or self::section or self::networks-step][1]"
                        f"[.//*[contains(normalize-space(.), '{label}')]]]"
                    )
                    if not cbs:
                        cbs = d.find_elements(
                            By.XPATH,
                            f"//*[contains(normalize-space(.), '{label}')]/ancestor-or-self::*[1]//material-checkbox"
                        )
                    for c in cbs:
                        if c.is_displayed():
                            return c
                except Exception:
                    pass
                return None

            for cls_name, label in NETWORK_LABELS:
                unchecked = False
                for attempt in range(3):
                    c = find_network_cb(cls_name, label)
                    if c is None:
                        self.tracker.log(f"Khong tim thay checkbox '{label}'", "warn")
                        break
                    try:
                        if not is_checkbox_ticked(c):
                            self.tracker.log(f"'{label}' DA unchecked san — skip", "success")
                            unchecked = True
                            break
                    except Exception:
                        pass
                    try:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", c)
                        time.sleep(0.7)
                        # Selenium native click truoc de trigger material listener
                        try:
                            c.click()
                        except Exception:
                            try:
                                action_click(c)
                            except Exception:
                                js_click(c)
                        self.tracker.log(f"Da bo tick: {label} (lan {attempt + 1})", "success")
                    except Exception as e:
                        self.tracker.log(f"Loi click '{label}': {e}", "warn")
                        time.sleep(1)
                        continue
                    # QUAN TRONG: Doi 2s cho Google auto-save xong
                    time.sleep(2)
                    # Verify: tim lai checkbox va check state
                    try:
                        c2 = find_network_cb(cls_name, label)
                        if c2 is None or not is_checkbox_ticked(c2):
                            self.tracker.log(f"Verified: '{label}' da unchecked", "success")
                            unchecked = True
                            break
                        else:
                            self.tracker.log(f"'{label}' VAN tick — retry (lan {attempt + 1})", "warn")
                    except Exception:
                        unchecked = True
                        break
                if not unchecked:
                    self.tracker.log(f"KHONG bo tich duoc '{label}' sau 3 lan", "error")
            run_verify("settings")
            break
        else:
            self.tracker.log("[SKIP] Buoc 15: Campaign Settings (start_step)", "warn")

        # === BUOC 16: Locations ===
        while _run("locations"):
            self.tracker.set_current(step="Buoc 16: Locations")
            time.sleep(1.2)  # buffer cho DOM on dinh
            check_all()
            target_locs = campaign_config.get("target_locations", [])
            exclude_locs = campaign_config.get("exclude_locations", [])

            if target_locs or exclude_locs:
                try:
                    WebDriverWait(d, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Enter another location')]"))
                    ).click()
                    time.sleep(0.7)
                    WebDriverWait(d, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Advanced search')]"))
                    ).click()
                    time.sleep(1)

                    # Tick bulk
                    bulk_cb = d.find_element(By.XPATH, "//material-checkbox[contains(@class, 'bulk-locations-checkbox')]")
                    if bulk_cb.get_attribute("aria-checked") != "true":
                        js_click(bulk_cb)
                        time.sleep(0.3)

                    BULK_TA = "//bulk-location-input//textarea[contains(@class, 'textarea')]"
                    SEARCH_BTN = "//bulk-location-input//material-button[contains(@class, 'search-button')]"
                    TARGET_ALL = "//material-button[.//div[contains(text(), 'Target all')] or .//span[contains(text(), 'Target all')]]"
                    EXCLUDE_ALL = "//material-button[.//div[contains(text(), 'Exclude all')] or .//span[contains(text(), 'Exclude all')]]"

                    def bulk_search(locs, action_xpath, label):
                        ta = WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.XPATH, BULK_TA)))
                        ta.click()
                        time.sleep(0.3)
                        loc_text = "\n".join(locs) if isinstance(locs, list) else str(locs).replace("|", "\n")
                        js_set_textarea(ta, loc_text)
                        time.sleep(1)
                        WebDriverWait(d, 15).until(
                            lambda drv: drv.find_element(By.XPATH, SEARCH_BTN).get_attribute("aria-disabled") != "true"
                        )
                        js_click(d.find_element(By.XPATH, SEARCH_BTN))
                        time.sleep(8)
                        WebDriverWait(d, 15).until(EC.element_to_be_clickable((By.XPATH, action_xpath)))
                        js_click(d.find_element(By.XPATH, action_xpath))
                        time.sleep(1)
                        count = len(locs) if isinstance(locs, list) else locs.count("|") + 1
                        self.tracker.log(f"Da {label} {count} locations", "success")

                    if target_locs:
                        bulk_search(target_locs, TARGET_ALL, "target")

                    if exclude_locs:
                        # Clear textarea cu
                        try:
                            ta = d.find_element(By.XPATH, BULK_TA)
                            ta.click()
                            time.sleep(0.2)
                            js_set_textarea(ta, "")
                            time.sleep(0.3)
                        except Exception:
                            pass
                        bulk_search(exclude_locs, EXCLUDE_ALL, "exclude")

                    # Save — tim nut Save (khong phai btn-yes vi selector co the sai)
                    time.sleep(0.5)
                    for b in d.find_elements(By.XPATH, "//material-button | //button"):
                        try:
                            if b.is_displayed() and b.text.strip() == "Save":
                                js_click(b)
                                self.tracker.log("Da save locations", "success")
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
            run_verify("locations")
            break
        else:
            self.tracker.log("[SKIP] Buoc 16: Locations (start_step)", "warn")

        # === BUOC 17: Xoa English -> All languages ===
        while _run("languages"):
            self.tracker.set_current(step="Buoc 17: Languages")
            time.sleep(1.2)  # buffer cho DOM on dinh
            removed = False
            # Nhieu selector fallback — Google co the doi attribute
            xpaths = [
                "//div[@aria-label='English remove']",
                "//button[@aria-label='Remove English']",
                "//*[@aria-label='Remove English']",
                "//material-chip[contains(., 'English')]//*[@aria-label[contains(., 'remove') or contains(., 'Remove')]]",
                "//material-chip[contains(., 'English')]//material-icon",
                "//*[contains(@class, 'chip')][contains(., 'English')]//*[contains(@class, 'close') or contains(@class, 'remove')]",
            ]
            for xp in xpaths:
                if removed:
                    break
                try:
                    for el in d.find_elements(By.XPATH, xp):
                        if el.is_displayed():
                            js_click(el)
                            self.tracker.log(f"Da xoa English -> All languages (selector: {xp[:50]}...)", "success")
                            time.sleep(0.3)
                            removed = True
                            break
                except Exception:
                    pass
            if not removed:
                self.tracker.log("Khong tim thay nut X cua English chip", "warn")
            run_verify("languages")
            break
        else:
            self.tracker.log("[SKIP] Buoc 17: Languages (start_step)", "warn")

        # === BUOC 18-20: Next > Next > Skip ===
        while _run("next_skip"):
            for step_name, btn_text in [("Buoc 18: Next", "Next"), ("Buoc 19: Skip AI Max", "Next"), ("Buoc 20: Skip keyword gen", "Skip")]:
                self.tracker.set_current(step=step_name)
                time.sleep(1.2)  # buffer cho DOM on dinh
                check_all()
                if not click_button(btn_text):
                    click_button("Next")
                time.sleep(8)
                check_all()
            run_verify("next_skip")
            break
        else:
            self.tracker.log("[SKIP] Buoc 18-20: Next/Skip (start_step)", "warn")

        # === BUOC 21: Keywords + Ads ===
        while _run("keywords_ads"):
            self.tracker.set_current(step="Buoc 21: Keywords + Ads")
            time.sleep(1.2)  # buffer cho DOM on dinh
            check_all()
            time.sleep(3)

            # Ad group name (neu co)
            adgroup_name = campaign_config.get("adgroup_name") or campaign_config.get("adgroupName")
            if adgroup_name:
                for xp in [
                    "//input[@aria-label='Ad group name']",
                    "//input[contains(@aria-label, 'Ad group')]",
                    "//ad-group-name-input//input",
                ]:
                    try:
                        for inp in d.find_elements(By.XPATH, xp):
                            if inp.is_displayed():
                                clear_and_type(inp, adgroup_name)
                                self.tracker.log(f"Da dien Ad group name: {adgroup_name}", "success")
                                break
                        else:
                            continue
                        break
                    except Exception:
                        pass

            # Keywords
            keywords = campaign_config.get("keywords", [])
            if keywords:
                try:
                    kw_ta = WebDriverWait(d, 15).until(
                        EC.presence_of_element_located((By.XPATH, '//textarea[contains(@aria-label, "Enter or paste keywords")]'))
                    )
                    kw_ta.click()
                    time.sleep(0.3)
                    kw_text = "\n".join(keywords) if isinstance(keywords, list) else str(keywords)
                    kw_ta.send_keys(kw_text)
                    self.tracker.log(f"Da dien {len(keywords)} keywords", "success")
                except Exception as e:
                    self.tracker.log(f"Loi keywords: {e}", "warn")
                time.sleep(0.3)

            # Final URL
            final_url = campaign_config.get("final_url", "")
            if final_url:
                try:
                    url_input = WebDriverWait(d, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '//input[@aria-label="Final URL"]'))
                    )
                    clear_and_type(url_input, final_url)
                    self.tracker.log(f"Da dien Final URL", "success")
                except Exception as e:
                    self.tracker.log(f"Loi Final URL: {e}", "warn")
                time.sleep(0.3)

            # Headlines — dien het toi da, click Add neu thieu o
            headlines = campaign_config.get("headlines", [])
            if headlines:
                try:
                    HL_XPATH = '//section[contains(@class, "headline")]//input'
                    WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, HL_XPATH)))
                    time.sleep(0.5)
                    section = d.find_element(By.XPATH, '//section[contains(@class, "headline")]')
                    filled = 0
                    for hl in headlines:
                        inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                        if filled >= len(inps):
                            try:
                                for ad in section.find_elements(By.XPATH, ".//div[contains(@class, 'add')]"):
                                    if ad.is_displayed() and "Headline" in ad.text:
                                        js_click(ad)
                                        time.sleep(0.3)
                                        break
                                inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                            except Exception:
                                break
                        if filled < len(inps):
                            inp = inps[filled]
                            d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", inp)
                            time.sleep(0.8)
                            try:
                                d.find_element(By.TAG_NAME, "body").click()
                                time.sleep(0.3)
                            except Exception:
                                pass
                            has_dki = "{" in str(hl)
                            try:
                                clear_and_type(inp, hl)
                            except Exception:
                                js_click(inp)
                                time.sleep(0.3)
                                inp.send_keys(Keys.CONTROL, "a")
                                time.sleep(0.2)
                                inp.send_keys(str(hl))
                            # Dong popup Dynamic Keyword Insertion neu headline co '{'
                            if has_dki:
                                try:
                                    inp.send_keys(Keys.ESCAPE)
                                    time.sleep(0.3)
                                except Exception:
                                    pass
                            filled += 1
                            time.sleep(0.5)
                    self.tracker.log(f"Da dien {filled}/{len(headlines)} headlines", "success")
                except Exception as e:
                    self.tracker.log(f"Loi headlines: {e}", "warn")

            # Descriptions — dien het toi da
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
                                        time.sleep(0.3)
                                        break
                                visible = [dd for dd in d.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if dd.is_displayed()]
                            except Exception:
                                break
                        if filled < len(visible):
                            clear_and_type(visible[filled], desc)
                            filled += 1
                            time.sleep(0.5)
                    self.tracker.log(f"Da dien {filled}/{len(descriptions)} descriptions", "success")
                except Exception as e:
                    self.tracker.log(f"Loi descriptions: {e}", "warn")

            # Next — check 2FA truoc vi hay nhay ra o buoc 21
            check_all()
            click_button("Next")
            time.sleep(10)
            check_all()

            # Sau 2FA co the bi reset — check trang hien tai truc tiep
            for retry_after_21 in range(3):
                on_budget = on_page(
                    "//material-radio[contains(., 'Set custom budget')] | "
                    "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"
                )
                on_publish = False
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    try:
                        if b.is_displayed() and "Publish campaign" in b.text:
                            on_publish = True
                            break
                    except Exception:
                        pass
                on_keywords = on_page(
                    "//textarea[contains(@aria-label, 'keyword')] | "
                    "//input[@aria-label='Final URL']"
                )

                if on_budget:
                    self.tracker.log("Dang o trang Budget", "warn")
                    break
                elif on_publish:
                    self.tracker.log("Da o trang Review — skip Budget")
                    break
                elif on_keywords:
                    self.tracker.log(f"Van o Keywords (2FA reset?) — Next lai ({retry_after_21 + 1})", "warn")
                    click_button("Next")
                    time.sleep(10)
                    check_all()
                    continue
                else:
                    click_button("Next")
                    time.sleep(8)
                    check_all()
                    break
            run_verify("keywords_ads")
            break
        else:
            self.tracker.log("[SKIP] Buoc 21: Keywords + Ads (start_step)", "warn")

        # === BUOC 22: Budget ===
        while _run("budget"):
            self.tracker.set_current(step="Buoc 22: Budget")
            time.sleep(1.2)  # buffer cho DOM on dinh
            check_all()
            time.sleep(3)
            budget = campaign_config.get("budget", "5")

            # Click radio Set custom budget bang ActionChains
            for r in d.find_elements(By.TAG_NAME, "material-radio"):
                try:
                    if r.is_displayed() and "Set custom budget" in r.text:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", r)
                        time.sleep(0.7)
                        action_click(r)
                        time.sleep(0.5)
                        break
                except Exception:
                    pass

            # Expand panel
            panels = d.find_elements(By.XPATH, "//proactive-budget-recommendation-picker//material-expansionpanel")
            for p in reversed(panels):
                try:
                    if p.is_displayed() and "Set custom" in p.text:
                        header = p.find_element(By.XPATH, ".//div[contains(@class, 'header')]")
                        action_click(header)
                        time.sleep(1)
                        break
                except Exception:
                    pass

            # Dien budget — nhieu selector fallback
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
                            d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", el)
                            time.sleep(0.8)
                            clear_and_type(el, budget)
                            self.tracker.log(f"Da dien budget: ${budget}", "success")
                            budget_filled = True
                            break
                except Exception:
                    pass
            if not budget_filled:
                time.sleep(5)
                try:
                    bi = WebDriverWait(d, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"))
                    )
                    clear_and_type(bi, budget)
                    self.tracker.log(f"Da dien budget (retry): ${budget}", "success")
                except Exception:
                    self.tracker.log("Khong tim thay budget input", "warn")

            # Verify budget value — retry neu Material input nuot ky tu
            for verify_try in range(3):
                try:
                    bi = d.find_element(By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]")
                    val = (bi.get_attribute("value") or "").strip()
                    if val == str(budget) or val.replace(",", "").replace(".00", "") == str(budget):
                        self.tracker.log(f"Budget verified: {val}", "success")
                        break
                    self.tracker.log(f"Budget value sai ({val} != {budget}) — dien lai (lan {verify_try + 1})", "warn")
                    clear_and_type(bi, budget)
                    time.sleep(1)
                except Exception:
                    break

            # Verify truoc khi di tiep
            run_verify("budget")

            # Next -> Review — CHI khi khong phai single-step mode
            check_all()
            if not _single_step:
                click_button("Next")
                time.sleep(8)
                check_all()
            else:
                self.tracker.log("Single-step mode: KHONG click Next sau Budget", "warn")
            break
        else:
            self.tracker.log("[SKIP] Buoc 22: Budget (start_step)", "warn")

        # === BUOC 23 + SAU PUBLISH: Publish + post-handling ===
        if _run("publish"):
            self.tracker.set_current(step="Buoc 23: Publish")
            time.sleep(1.2)  # buffer cho DOM on dinh

            # Doi nut Publish — neu 2FA reset hoac Fix errors, scan lai va xu ly
            budget = campaign_config.get("budget", "5")
            for wait_round in range(12):
                check_all()
                check_login()

                # Tim nut Publish — uu tien button enabled
                found = False
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    try:
                        if b.is_displayed() and "Publish campaign" in b.text:
                            if b.get_attribute("aria-disabled") != "true" and b.is_enabled():
                                found = True
                                break
                    except Exception:
                        pass
                if found:
                    break

                # Chua thay Publish — check trang hien tai truc tiep
                on_budget = on_page(
                    "//material-radio[contains(., 'Set custom budget')] | "
                    "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"
                )
                on_keywords = on_page(
                    "//textarea[contains(@aria-label, 'keyword')] | "
                    "//input[@aria-label='Final URL'] | "
                    "//section[contains(@class, 'headline')]//input"
                )
                on_settings = on_page(
                    "//material-checkbox[contains(@class, 'search-checkbox')] | "
                    "//material-checkbox[contains(@class, 'display-checkbox')]"
                )

                if on_budget:
                    self.tracker.log("Dang o Budget — check + Next...")
                    try:
                        bi = d.find_element(By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]")
                        if bi.is_displayed():
                            val = bi.get_attribute("value") or ""
                            if not val or val == "0":
                                clear_and_type(bi, budget)
                                self.tracker.log(f"Dien lai budget: ${budget}")
                    except Exception:
                        pass
                    click_button("Next")
                    time.sleep(8)
                    check_all()
                    continue

                elif on_keywords:
                    self.tracker.log("Dang o Keywords/Ads — Next...")
                    click_button("Next")
                    time.sleep(10)
                    check_all()
                    continue

                elif on_settings:
                    self.tracker.log("Dang o Settings — Next...")
                    click_button("Next")
                    time.sleep(10)
                    check_all()
                    continue

                self.tracker.log(f"Doi Publish... ({(wait_round + 1) * 5}s)")
                time.sleep(5)

            # Click Publish (retry 5 lan — xu ly Fix errors dialog neu co)
            for attempt in range(5):
                # QUAN TRONG: check dialog Fix errors TRUOC khi click Publish
                # Dialog de len Publish button nen phai dong dialog truoc
                check_all()

                # Tim va click Publish — phai enabled
                pub_clicked = False
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    try:
                        if not b.is_displayed() or "Publish campaign" not in b.text:
                            continue
                        if b.get_attribute("aria-disabled") == "true" or not b.is_enabled():
                            self.tracker.log(f"Publish dang disabled — skip (lan {attempt + 1})", "warn")
                            continue
                        d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", b)
                        time.sleep(1)
                        action_click(b)
                        self.tracker.log(f"Da click Publish! (lan {attempt + 1})", "success")
                        pub_clicked = True
                        time.sleep(3)
                        # Xu ly dialog "Publish campaign that cannot run ads?" — click Publish trong dialog
                        try:
                            for _ in range(3):
                                confirm_clicked = False
                                for dlg in d.find_elements(By.XPATH, "//material-dialog"):
                                    try:
                                        if not dlg.is_displayed():
                                            continue
                                        dlg_text = (dlg.text or "").lower()
                                        if "cannot run ads" in dlg_text or "can't run ads" in dlg_text or "missing information" in dlg_text:
                                            self.tracker.log("[PUBLISH] Dialog 'cannot run ads' — click Publish trong dialog")
                                            for btn in dlg.find_elements(By.XPATH, ".//material-button | .//button"):
                                                try:
                                                    if btn.is_displayed() and btn.text.strip().lower() == "publish":
                                                        js_click(btn)
                                                        self.tracker.log("[PUBLISH] Da confirm Publish trong dialog", "success")
                                                        confirm_clicked = True
                                                        time.sleep(3)
                                                        break
                                                except Exception:
                                                    pass
                                            break
                                    except Exception:
                                        pass
                                if not confirm_clicked:
                                    break
                                time.sleep(2)
                        except Exception as e:
                            self.tracker.log(f"[PUBLISH] Loi xu ly confirm dialog: {e}", "warn")
                        time.sleep(7)
                        break
                    except Exception:
                        pass

                if not pub_clicked:
                    # Khong tim thay Publish — co the dialog che, thu Next
                    click_button("Next")
                    time.sleep(10)

                check_all()
                if "New campaign" not in d.title and "Search campaign" not in d.title:
                    break
                self.tracker.log(f"Van o trang Review (lan {attempt + 1})", "warn")
                time.sleep(5)

            # === SAU PUBLISH: Policy Review + Google Tag ===
            time.sleep(5)
            check_all()

            # Policy Review: "Your campaign is published, but it can't run yet" -> Next
            for _ in range(3):
                if "policy" in d.current_url.lower() or "can't run" in (d.page_source[:5000] if d.page_source else ""):
                    self.tracker.log("Trang Policy Review — an Next")
                    click_button("Next")
                    time.sleep(5)
                    check_all()
                else:
                    break

            # Google Tag: /aw/signup/tagging -> Close (X)
            time.sleep(3)
            try:
                close_btn = d.find_element(By.XPATH, "//material-button[@aria-label='Close']")
                if close_btn.is_displayed():
                    action_click(close_btn)
                    self.tracker.log("Da dong Google Tag")
                    time.sleep(3)
            except Exception:
                pass

            # Dong popup "Campaign created / What's next" neu co
            try:
                for dlg in d.find_elements(By.XPATH, "//material-dialog"):
                    if not dlg.is_displayed():
                        continue
                    dlg_text = dlg.text.lower()
                    if "campaign created" in dlg_text or "what's next" in dlg_text or "congratulations" in dlg_text:
                        for cb in dlg.find_elements(By.XPATH, ".//material-button[@aria-label='Close'] | .//material-button[.//*[contains(normalize-space(.), 'Done')]] | .//button[.//*[contains(normalize-space(.), 'Done')]]"):
                            if cb.is_displayed():
                                js_click(cb)
                                self.tracker.log("Da dong popup Campaign created")
                                time.sleep(2)
                                break
                        break
            except Exception:
                pass

            # Verify publish thanh cong truoc khi upsert DB
            time.sleep(3)
            run_verify("publish")
            cur_url = d.current_url.lower()
            cur_title = (d.title or "").lower()
            publish_ok = False

            # Dau hieu thanh cong: URL sang /campaigns (khong phai /new), /overview, hoac banner/dialog "published"
            if "/aw/campaigns" in cur_url and "/new" not in cur_url:
                publish_ok = True
            elif "/aw/overview" in cur_url:
                publish_ok = True
            elif "published" in cur_title or "policy" in cur_url or "signup/tagging" in cur_url:
                publish_ok = True
            else:
                try:
                    if "campaign created" in (d.page_source[:8000] or "").lower() or \
                       "campaign is published" in (d.page_source[:8000] or "").lower():
                        publish_ok = True
                except Exception:
                    pass

            if publish_ok:
                upsert_campaign(self.customer_id, name, status="published")
                self.tracker.log(f"Campaign '{name}' da duoc publish thanh cong!", "success")
                return True
            else:
                self.tracker.log(
                    f"Publish KHONG xac nhan duoc (URL: {d.current_url[:120]}, title: {d.title[:80]}) — khong update DB",
                    "error",
                )
                upsert_campaign(self.customer_id, name, status="failed",
                                notes="Publish clicked but success not verified")
                return False
        else:
            self.tracker.log("[SKIP] Buoc 23: Publish (start_step)", "warn")
            return True
