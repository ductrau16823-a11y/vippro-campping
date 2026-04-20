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

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api_helpers import upsert_campaign
from status_tracker import StatusTracker


def _is_window_closed_exc(err_text):
    """True neu exception text la do browser/window/session dong."""
    if not err_text:
        return False
    s = str(err_text).lower()
    return (
        "no such window" in s
        or "target window already closed" in s
        or "web view not found" in s
        or "invalid session id" in s
        or "chrome not reachable" in s
        or "disconnected: not connected to devtools" in s
        or "session deleted" in s
    )


class WindowClosedError(Exception):
    """Raised khi browser window/session dong giua chung — caller skip TK."""
    pass


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
        name = f"{base_name} {camp_index}"
        self.tracker.log(f"=== Bat dau tao campaign: {name} (#{camp_index}) ===")

        # Determine start index tu start_step
        _start_idx = 0
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

        # ==================== V4-PORTED HELPERS (Buoc 14+15) ====================

        def _esc(text):
            """XPath string literal — dung concat neu co ca " va '."""
            if '"' not in text:
                return f'"{text}"'
            if "'" not in text:
                return f"'{text}'"
            parts = text.split('"')
            return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"

        def _visible(els):
            out = []
            for e in els:
                try:
                    if e.is_displayed():
                        out.append(e)
                except Exception:
                    pass
            return out

        def _safe_click(el):
            try:
                d.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
                time.sleep(0.3)
            except Exception:
                pass
            for fn in (lambda: el.click(), lambda: action_click(el), lambda: js_click(el)):
                try:
                    fn()
                    return True
                except Exception:
                    pass
            return False

        def pick_dropdown(current_text, new_text):
            """Mo dropdown dang hien current_text -> chon item new_text. Return True/False."""
            cur = _esc(current_text)
            new = _esc(new_text)
            dbs = _visible(d.find_elements(
                By.XPATH,
                f"//dropdown-button[contains(normalize-space(.), {cur})] | "
                f"//material-dropdown-select[contains(normalize-space(.), {cur})]//dropdown-button | "
                f"//*[@role='combobox'][contains(normalize-space(.), {cur})]"
            ))
            if not dbs:
                return False
            _safe_click(dbs[0])
            time.sleep(1.5)
            for xp in (
                f"//material-select-dropdown-item[normalize-space()={new}]",
                f"//*[@role='option'][normalize-space()={new}]",
                f"//material-select-dropdown-item[contains(normalize-space(.), {new})]",
                f"//*[@role='option'][contains(normalize-space(.), {new})]",
            ):
                for item in _visible(d.find_elements(By.XPATH, xp)):
                    if _safe_click(item):
                        time.sleep(1)
                        return True
            return False

        def fill_input_near(label_text, value):
            """Tim input gan label_text roi dien value. Return True/False."""
            t = _esc(label_text)
            for xp in (
                f"//label[contains(normalize-space(.), {t})]/following::input[not(@type='hidden')][1]",
                f"//*[normalize-space(text())={t}]/ancestor::*[self::div or self::section or self::material-input][1]//input[not(@type='hidden')]",
                f"//*[contains(normalize-space(text()), {t})]/following::input[not(@type='hidden')][1]",
                f"//input[@aria-label={t}]",
                f"//input[contains(@aria-label, {t})]",
                f"//input[@placeholder={t}]",
            ):
                for inp in _visible(d.find_elements(By.XPATH, xp)):
                    try:
                        clear_and_type(inp, value)
                        return True
                    except Exception:
                        try:
                            js_fill_input(inp, value)
                            return True
                        except Exception:
                            pass
            return False

        def _find_checkbox_with_label(label_text):
            t = _esc(label_text)
            for xp in (
                f"//material-checkbox[contains(normalize-space(.), {t})]",
                f"//mat-checkbox[contains(normalize-space(.), {t})]",
                f"//*[@role='checkbox'][contains(normalize-space(.), {t})]",
            ):
                for el in _visible(d.find_elements(By.XPATH, xp)):
                    return el
            return None

        def tick_by_label(label_text):
            el = _find_checkbox_with_label(label_text)
            if el is None:
                return False
            if not is_checkbox_ticked(el):
                _safe_click(el)
                time.sleep(0.5)
            return True

        def untick_by_label(label_text):
            el = _find_checkbox_with_label(label_text)
            if el is None:
                return False
            if is_checkbox_ticked(el):
                _safe_click(el)
                time.sleep(0.5)
            return True

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
            """Check 2FA + popup + draft truoc moi buoc.
            BOC trong thread voi timeout 15s — neu Selenium block giua page transition thi skip."""
            import threading

            def _body():
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

            t = threading.Thread(target=_body, daemon=True)
            t.start()
            t.join(timeout=15.0)
            if t.is_alive():
                self.tracker.log("[CHECK_ALL] TIMEOUT 15s — skip, tiep tuc flow", "warn")

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

        # === BUOC 14: Bidding (v4-ported) ===
        while _run("bidding"):
            self.tracker.set_current(step="Buoc 14: Bidding")
            self.tracker.log(">>> VAO BUOC 14: Bidding")
            time.sleep(2)
            bidding = campaign_config.get("bidding", "maximize_clicks")
            cpc = campaign_config.get("cpc", "")
            self.tracker.log(f"[14] bidding='{bidding}' cpc='{cpc}'")

            # 1. Chon bidding strategy (Clicks) — Uu tien "Change bid strategy" link neu co
            if "click" in bidding.lower():
                picked = False

                # UU TIEN: Click "Change bid strategy" link neu visible (dam bao commit strategy)
                change_link_clicked = False
                # Chi chon element la leaf (khong co child cung text) — clickable that su
                for xp in (
                    "//a[normalize-space(.)='Change bid strategy']",
                    "//material-button[normalize-space(.)='Change bid strategy']",
                    "//button[normalize-space(.)='Change bid strategy']",
                    "//*[@role='link' and normalize-space(.)='Change bid strategy']",
                    "//span[normalize-space(.)='Change bid strategy']",
                    "//a[contains(normalize-space(.), 'Change bid strategy')]",
                    "//material-button[contains(normalize-space(.), 'Change bid strategy')]",
                ):
                    try:
                        els = _visible(d.find_elements(By.XPATH, xp))
                        self.tracker.log(f"[14] XPath '{xp[:50]}...' tim thay {len(els)} element")
                        for el in els:
                            # Neu element la container (chua nhieu child), tim parent <a> gan nhat
                            try:
                                tag = el.tag_name.lower()
                            except Exception:
                                tag = ""
                            target = el
                            if tag not in ("a", "button", "material-button"):
                                try:
                                    anc = el.find_element(By.XPATH, "./ancestor-or-self::a[1] | ./ancestor-or-self::material-button[1] | ./ancestor-or-self::button[1]")
                                    if anc:
                                        target = anc
                                except Exception:
                                    pass
                            try:
                                clicked = _safe_click(target)
                            except Exception as _ce:
                                # Stale element sau click = click co the da trigger DOM re-render -> coi nhu OK
                                if "stale" in str(_ce).lower():
                                    clicked = True
                                    self.tracker.log("[14] Click Change bid strategy trigger DOM re-render (stale OK)", "success")
                                else:
                                    clicked = False
                            if clicked:
                                change_link_clicked = True
                                try:
                                    tgname = target.tag_name
                                except Exception:
                                    tgname = "?"
                                self.tracker.log(f"[14] Da click 'Change bid strategy' (tag={tgname})", "success")
                                time.sleep(2)
                                break
                        if change_link_clicked:
                            break
                    except Exception as _e:
                        err_str = str(_e)
                        if "stale" in err_str.lower():
                            # Stale tu buoc tim element -> DOM da thay doi, co the do click truoc do thanh cong
                            change_link_clicked = True
                            self.tracker.log("[14] Stale element -> coi nhu click Change bid strategy thanh cong", "success")
                            time.sleep(1.5)
                            break
                        self.tracker.log(f"[14] Loi selector: {err_str[:100]}", "warn")

                if change_link_clicked:
                    # Sau khi click link -> panel expand, kiem tra dropdown co mo khong
                    # Neu co dropdown-button hien ra va text khac 'Clicks' -> pick Clicks
                    # Neu khong, giu nguyen strategy (la Maximize clicks) + panel expand de dien CPC
                    time.sleep(0.8)
                    dbs2 = _visible(d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"))
                    need_pick = False
                    if dbs2:
                        cur_txt = (dbs2[0].text or "").strip()
                        if "Click" not in cur_txt and cur_txt:
                            need_pick = True
                            _safe_click(dbs2[0])
                            time.sleep(1.2)
                    if need_pick:
                        for xp in (
                            "//material-select-dropdown-item[normalize-space()='Clicks']",
                            "//*[@role='option'][normalize-space()='Clicks']",
                            "//material-select-dropdown-item[contains(normalize-space(.), 'Clicks')]",
                        ):
                            for item in _visible(d.find_elements(By.XPATH, xp)):
                                if _safe_click(item):
                                    picked = True
                                    self.tracker.log("[14] Da chon Clicks qua 'Change bid strategy'", "success")
                                    time.sleep(1)
                                    break
                            if picked:
                                break
                    else:
                        picked = True
                        self.tracker.log("[14] Panel da expand, strategy=Maximize clicks OK", "success")

                # Neu khong co link "Change bid strategy" -> fallback kiem tra + pick dropdown
                if not picked:
                    already_clicks = len(_visible(d.find_elements(
                        By.XPATH,
                        "//dropdown-button[normalize-space(.)='Clicks'] | "
                        "//material-dropdown-select[.//dropdown-button[normalize-space(.)='Clicks']]"
                    ))) > 0
                else:
                    already_clicks = False  # da pick xong qua link
                if already_clicks and not picked:
                    self.tracker.log("[14] Dropdown da la Clicks — skip doi", "success")
                    picked = True
                elif not picked:
                    # Tier 1: Thu 3 default text hay gap
                    picked = pick_dropdown("Conversions", "Clicks")
                    if not picked:
                        picked = pick_dropdown("Conversion value", "Clicks")
                    if not picked:
                        picked = pick_dropdown("Impression share", "Clicks")
                    # Tier 2: Fallback v1-style — click dropdown-button dau tien trong material-dropdown-select
                    if not picked:
                        self.tracker.log("[14] 3 default miss — thu fallback v1-style", "warn")
                        dbs = _visible(d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"))
                        self.tracker.log(f"[14] Fallback: tim thay {len(dbs)} dropdown-button visible")
                        if dbs:
                            cur_txt = (dbs[0].text or "").strip()[:60]
                            self.tracker.log(f"[14] Fallback: dropdown dang hien '{cur_txt}'")
                            _safe_click(dbs[0])
                            time.sleep(1.5)
                            for xp in (
                                "//material-select-dropdown-item[normalize-space()='Clicks']",
                                "//*[@role='option'][normalize-space()='Clicks']",
                                "//material-select-dropdown-item[contains(normalize-space(.), 'Clicks')]",
                            ):
                                for item in _visible(d.find_elements(By.XPATH, xp)):
                                    if _safe_click(item):
                                        picked = True
                                        time.sleep(1)
                                        break
                                if picked:
                                    break
                    # Tier 3: Click "Change bid strategy" link -> wait dialog -> pick Clicks
                    if not picked:
                        self.tracker.log("[14] Thu Tier 3: click 'Change bid strategy' link")
                        link_clicked = False
                        for xp in (
                            "//a[contains(normalize-space(.), 'Change bid strategy')]",
                            "//*[@role='link'][contains(normalize-space(.), 'Change bid strategy')]",
                            "//*[contains(@class, 'link')][contains(normalize-space(.), 'Change bid strategy')]",
                            "//span[contains(normalize-space(.), 'Change bid strategy')]",
                            "//*[contains(normalize-space(.), 'Change bid strategy')]",
                        ):
                            try:
                                for el in _visible(d.find_elements(By.XPATH, xp)):
                                    if _safe_click(el):
                                        link_clicked = True
                                        self.tracker.log("[14] Da click 'Change bid strategy'", "success")
                                        time.sleep(2)
                                        break
                                if link_clicked:
                                    break
                            except Exception:
                                pass

                        if link_clicked:
                            # Dialog/dropdown da mo -> tim dropdown-button va pick Clicks
                            time.sleep(1)
                            dbs2 = _visible(d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"))
                            if dbs2:
                                _safe_click(dbs2[0])
                                time.sleep(1.2)
                            for xp in (
                                "//material-select-dropdown-item[normalize-space()='Clicks']",
                                "//*[@role='option'][normalize-space()='Clicks']",
                                "//material-select-dropdown-item[contains(normalize-space(.), 'Clicks')]",
                                "//*[contains(normalize-space(.), 'Clicks')][@role='option' or contains(@class, 'item')]",
                            ):
                                for item in _visible(d.find_elements(By.XPATH, xp)):
                                    if _safe_click(item):
                                        picked = True
                                        self.tracker.log("[14] Tier 3: Da chon Clicks", "success")
                                        time.sleep(1)
                                        break
                                if picked:
                                    break
                    if picked:
                        self.tracker.log("[14] Da chon Clicks bidding", "success")
                    else:
                        self.tracker.log("[14] KHONG chon duoc dropdown bidding (ca 4 tier)", "error")

            # 2. Tick + dien max CPC (neu co)
            if cpc:
                if tick_by_label("maximum cost per click"):
                    self.tracker.log("[14] Tick max CPC OK", "success")
                    time.sleep(1)
                filled = fill_input_near("Maximum CPC", cpc)
                if not filled:
                    filled = fill_input_near("Max. CPC", cpc)
                if not filled:
                    filled = fill_input_near("max CPC", cpc)
                if filled:
                    self.tracker.log(f"[14] Da dien CPC: {cpc}", "success")
                else:
                    self.tracker.log("[14] KHONG dien duoc CPC", "warn")

            # 3. Click Next
            time.sleep(2)
            click_button("Next")
            self.tracker.log("[14] Da click Next", "success")
            time.sleep(4)
            break
        else:
            self.tracker.log("[SKIP] Buoc 14: Bidding (start_step)", "warn")

        # === BUOC 15: Campaign Settings (Networks) — v4-ported ===
        while _run("settings"):
            self.tracker.set_current(step="Buoc 15: Campaign Settings")
            self.tracker.log(">>> VAO BUOC 15: Campaign Settings", "info")
            time.sleep(2)

            # Bo tick Search Partners + Display Network — class-based (v1-proven) + text fallback
            for cls_name in ("search-checkbox", "display-checkbox"):
                for c in _visible(d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls_name}')]")):
                    try:
                        if is_checkbox_ticked(c):
                            _safe_click(c)
                            self.tracker.log(f"[15] Da bo tick {cls_name}", "success")
                            time.sleep(1)
                        break
                    except Exception:
                        pass
            # Fallback text-based
            if untick_by_label("Search Partners"):
                self.tracker.log("[15] Bo tick Search Partners (text)", "success")
            if untick_by_label("Display Network"):
                self.tracker.log("[15] Bo tick Display Network (text)", "success")
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
            for _ in range(3):
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

                time.sleep(0.8)
                if not removed:
                    self.tracker.log("Khong tim thay nut X cua English chip", "warn")
                break
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

            # Sau 2FA, Google co the reset trang ve Bidding/Settings/Keywords — scan + Next cho toi khi ve Budget
            for pre_round in range(6):
                on_budget_now = on_page(
                    "//material-radio[contains(., 'Set custom budget')] | "
                    "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"
                )
                if on_budget_now:
                    break
                on_bidding_now = on_page(
                    "//material-dropdown-select//dropdown-button[contains(., 'Conversions') or contains(., 'Clicks') or contains(., 'Conversion value')] | "
                    "//*[contains(normalize-space(.), 'Change bid strategy')] | "
                    "//*[contains(normalize-space(.), 'What do you want to focus on')]"
                )
                on_keywords_now = on_page(
                    "//textarea[contains(@aria-label, 'keyword')] | "
                    "//input[@aria-label='Final URL'] | "
                    "//section[contains(@class, 'headline')]//input"
                )
                on_settings_now = on_page(
                    "//material-checkbox[contains(@class, 'search-checkbox')] | "
                    "//material-checkbox[contains(@class, 'display-checkbox')]"
                )
                if on_bidding_now or on_keywords_now or on_settings_now:
                    where = "Bidding" if on_bidding_now else ("Keywords" if on_keywords_now else "Settings")
                    self.tracker.log(f"[22] 2FA da day ve {where} — Next de tien toi Budget", "warn")
                    click_button("Next")
                    time.sleep(6)
                    check_all()
                    continue
                # Khong detect duoc trang nao — cho them
                self.tracker.log(f"[22] Cho trang Budget render... ({(pre_round + 1) * 3}s)")
                time.sleep(3)

            # Click "Set custom budget" — thu nhieu cach vi layout moi la expansion panel
            def _click_set_custom_twice():
                # Cach 1: material-radio co text (layout cu)
                for r in d.find_elements(By.TAG_NAME, "material-radio"):
                    try:
                        if r.is_displayed() and "Set custom budget" in r.text:
                            d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", r)
                            time.sleep(0.6)
                            action_click(r)
                            time.sleep(0.9)
                            try:
                                action_click(r)
                                time.sleep(0.8)
                            except Exception:
                                pass
                            self.tracker.log("[22] Click Set custom qua material-radio", "success")
                            return True
                    except Exception:
                        pass

                # Cach 2: material-expansionpanel co header "Set custom budget" (layout moi)
                for xp in (
                    "//material-expansionpanel[.//*[contains(normalize-space(.), 'Set custom budget')]]",
                    "//*[contains(@class, 'expansionpanel')][.//*[contains(normalize-space(.), 'Set custom budget')]]",
                ):
                    try:
                        for p in d.find_elements(By.XPATH, xp):
                            if p.is_displayed():
                                d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", p)
                                time.sleep(0.6)
                                # Tim header de click
                                header = None
                                for h_xp in (".//div[contains(@class, 'header')]", ".//*[@class='header-container']", ".//*[contains(@class, 'panel-header')]"):
                                    try:
                                        hs = p.find_elements(By.XPATH, h_xp)
                                        if hs:
                                            header = hs[0]
                                            break
                                    except Exception:
                                        pass
                                target = header or p
                                action_click(target)
                                time.sleep(1.2)
                                # Click radio ben trong panel neu co
                                try:
                                    radios = p.find_elements(By.XPATH, ".//material-radio | .//*[@role='radio']")
                                    for r in radios:
                                        if r.is_displayed():
                                            action_click(r)
                                            time.sleep(0.6)
                                            break
                                except Exception:
                                    pass
                                self.tracker.log("[22] Click Set custom qua expansionpanel", "success")
                                return True
                    except Exception:
                        pass

                # Cach 3: click bat ky element hien thi co text "Set custom budget"
                for xp in (
                    "//*[normalize-space(.)='Set custom budget']",
                    "//*[contains(normalize-space(.), 'Set custom budget')]",
                ):
                    try:
                        for el in d.find_elements(By.XPATH, xp):
                            if el.is_displayed():
                                try:
                                    tag = el.tag_name.lower()
                                except Exception:
                                    tag = ""
                                # Skip ancestor chua nhieu text khac
                                txt = (el.text or "").strip()
                                if len(txt) > 100:
                                    continue
                                d.execute_script("arguments[0].scrollIntoView({block: 'center'})", el)
                                time.sleep(0.5)
                                action_click(el)
                                time.sleep(1)
                                self.tracker.log(f"[22] Click Set custom qua text (tag={tag})", "success")
                                return True
                    except Exception:
                        pass
                return False

            _click_set_custom_twice()

            # Poll budget input ready (toi 30s) — trang Budget co the load cham
            input_xpaths = [
                "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]",
                "//input[contains(@aria-label, 'amount') or contains(@aria-label, 'Amount')]",
                "//proactive-budget-recommendation-picker//input[@type='text']",
                "//proactive-budget-recommendation-picker//input",
                "//material-expansionpanel[.//span[contains(text(), 'Set custom')]]//input",
                "//material-expansionpanel[.//*[contains(., 'Set custom')]]//input",
                "//div[contains(@class, 'budget')]//input",
            ]

            def _find_budget_input():
                for xp in input_xpaths:
                    try:
                        for el in d.find_elements(By.XPATH, xp):
                            if el.is_displayed():
                                return el
                    except Exception:
                        pass
                return None

            deadline = time.time() + 30
            bi = None
            while time.time() < deadline:
                bi = _find_budget_input()
                if bi is not None:
                    break
                time.sleep(1)

            if bi is None:
                # Retry click Set custom (KHONG F5 — giu nguyen trang)
                self.tracker.log("[22] Khong tim thay budget input sau 30s -> retry click Set custom", "warn")
                check_all()
                _click_set_custom_twice()
                deadline2 = time.time() + 20
                while time.time() < deadline2:
                    bi = _find_budget_input()
                    if bi is not None:
                        break
                    time.sleep(1)

            if bi is not None:
                try:
                    d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", bi)
                    time.sleep(0.6)
                    clear_and_type(bi, budget)
                    self.tracker.log(f"Da dien budget: ${budget}", "success")
                except Exception as _e:
                    self.tracker.log(f"Loi dien budget: {_e}", "warn")
            else:
                self.tracker.log("Khong tim thay budget input (sau retry)", "warn")

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

            # Next -> Review (retry neu van con o Budget, toi 3 lan — KHONG F5)
            def _still_on_budget():
                try:
                    for el in d.find_elements(By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"):
                        if el.is_displayed():
                            return True
                except Exception:
                    pass
                return False

            for next_try in range(3):
                check_all()
                click_button("Next")
                # Poll 15s xem da roi Budget chua
                deadline_next = time.time() + 15
                left_budget = False
                while time.time() < deadline_next:
                    time.sleep(1)
                    if not _still_on_budget():
                        left_budget = True
                        break
                check_all()
                if left_budget:
                    self.tracker.log(f"[22] Da roi trang Budget (lan {next_try+1})", "success")
                    break
                self.tracker.log(f"[22] Van con o Budget sau Next (lan {next_try+1}) -> retry", "warn")
            break
        else:
            self.tracker.log("[SKIP] Buoc 22: Budget (start_step)", "warn")

        # === BUOC 23 + SAU PUBLISH: Publish + post-handling ===
        if _run("publish"):
            self.tracker.set_current(step="Buoc 23: Publish")
            time.sleep(1.2)  # buffer cho DOM on dinh

            budget = campaign_config.get("budget", "5")

            # GHEP NOI Buoc 22 -> Buoc 23: scan ngay trang hien tai
            # Neu van o Budget (Buoc 22 chua qua duoc) -> dien + Next cho toi khi sang Review
            check_all()
            for bridge_try in range(4):
                still_budget = False
                try:
                    for el in d.find_elements(By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"):
                        if el.is_displayed():
                            still_budget = True
                            # Dien lai budget neu trong
                            val = el.get_attribute("value") or ""
                            if not val or val == "0":
                                try:
                                    clear_and_type(el, budget)
                                    self.tracker.log(f"[23-bridge] Dien lai budget: ${budget}")
                                except Exception:
                                    pass
                            break
                except Exception:
                    pass
                if not still_budget:
                    break
                self.tracker.log(f"[23-bridge] Van o Budget -> Next (lan {bridge_try+1})", "warn")
                click_button("Next")
                time.sleep(6)
                check_all()

            # Doi nut Publish — neu 2FA reset hoac Fix errors, scan lai va xu ly
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

            # === VALIDATE REVIEW PAGE — fix lỗi truoc khi Publish ===
            def _scan_review_errors():
                """Scan trang Review, tra ve dict: {name_dup, networks_ticked, bidding_wrong, other_errors}."""
                errors = {
                    "name_dup": False,
                    "networks_text": "",
                    "bidding_text": "",
                    "languages_bad": False,
                    "red_errors": [],
                }
                try:
                    # 1. Name duplicate (text do)
                    for el in d.find_elements(By.XPATH, "//*[contains(text(), 'already exists') or contains(text(), 'A campaign with this name')]"):
                        if el.is_displayed():
                            errors["name_dup"] = True
                            break
                    # 2. Networks text (Search partners / Display Network)
                    for el in d.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'Search partners') or contains(normalize-space(.), 'Display Network')]"):
                        if el.is_displayed():
                            t = (el.text or "").strip()
                            if t and len(t) < 200:
                                errors["networks_text"] = t
                                break
                    # 3. Bidding text hien tai
                    for el in d.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'Maximize')]"):
                        if el.is_displayed():
                            t = (el.text or "").strip()
                            if t and "Maximize" in t and len(t) < 100:
                                errors["bidding_text"] = t
                                break
                    # 4. Languages "Item not found" (do)
                    for el in d.find_elements(By.XPATH, "//*[contains(text(), 'Item not found') or contains(text(), 'item not found')]"):
                        if el.is_displayed():
                            errors["languages_bad"] = True
                            break
                    # 5. Red errors khac (icon error / class error)
                    for el in d.find_elements(By.XPATH, "//*[contains(@class, 'error') and not(contains(@class, 'error-icon'))]"):
                        try:
                            if el.is_displayed():
                                t = (el.text or "").strip()
                                if t and 5 < len(t) < 200:
                                    errors["red_errors"].append(t)
                        except Exception:
                            pass
                except Exception as _e:
                    self.tracker.log(f"[REVIEW] Loi scan: {_e}", "warn")
                return errors

            def _fix_languages_from_review():
                """Trinh tu 6 buoc (anh xac nhan):
                1. Click red 'Item not found' tren Review
                2. Nhay sang trang Settings
                3. F5 tren Settings (EXCEPTION duy nhat — data campaign da luu)
                4. Fix Languages (xoa chip English/chip loi)
                5. Save/Back ve Review
                6. Re-scan (caller handle)
                """
                # BUOC 1: Click red 'Item not found' (hoac fallback cell Languages)
                clicked = False
                for xp in (
                    "//*[normalize-space(.)='Item not found']",
                    "//*[contains(normalize-space(.), 'Item not found')]",
                    "//*[contains(normalize-space(.), 'item not found')]",
                ):
                    try:
                        for el in d.find_elements(By.XPATH, xp):
                            if el.is_displayed():
                                t = (el.text or "").strip()
                                if len(t) > 200:
                                    continue
                                d.execute_script("arguments[0].scrollIntoView({block: 'center'})", el)
                                time.sleep(0.5)
                                if _safe_click(el):
                                    self.tracker.log("[REVIEW-LANG] Da click 'Item not found' -> navigate Settings")
                                    clicked = True
                                    break
                        if clicked:
                            break
                    except Exception:
                        pass
                # Fallback: click cell value canh label Languages
                if not clicked:
                    for xp in (
                        "//*[normalize-space(.)='Languages']/following-sibling::*[1]",
                        "//tr[.//*[normalize-space(.)='Languages']]//td[position()=2]",
                    ):
                        try:
                            for el in d.find_elements(By.XPATH, xp):
                                if el.is_displayed():
                                    if _safe_click(el):
                                        self.tracker.log("[REVIEW-LANG] Da click cell Languages (fallback)")
                                        clicked = True
                                        break
                            if clicked:
                                break
                        except Exception:
                            pass
                if not clicked:
                    self.tracker.log("[REVIEW-LANG] Khong click duoc red Languages", "warn")
                    return False

                # BUOC 2: Cho nhay sang Settings
                time.sleep(5)

                # BUOC 3: F5 tren Settings (EXCEPTION — chi duoc F5 o day)
                try:
                    self.tracker.log("[REVIEW-LANG] F5 tren Settings (exception duy nhat)")
                    d.refresh()
                    time.sleep(6)
                    check_all()
                except Exception as _re:
                    self.tracker.log(f"[REVIEW-LANG] F5 fail: {_re}", "warn")

                # BUOC 4: Fix Languages — xoa chip English/chip loi
                removed_any = False
                for _ in range(5):
                    found = False
                    for xp in (
                        "//div[@aria-label='English remove']",
                        "//button[@aria-label='Remove English']",
                        "//*[@aria-label='Remove English']",
                        "//material-chip[contains(., 'English')]//*[@aria-label[contains(., 'remove') or contains(., 'Remove')]]",
                        "//material-chip[contains(., 'English')]//material-icon",
                    ):
                        try:
                            for el in d.find_elements(By.XPATH, xp):
                                if el.is_displayed():
                                    js_click(el)
                                    self.tracker.log(f"[REVIEW-LANG] Xoa chip (selector: {xp[:50]}...)", "success")
                                    time.sleep(0.8)
                                    found = True
                                    removed_any = True
                                    break
                            if found:
                                break
                        except Exception:
                            pass
                    if not found:
                        break
                if not removed_any:
                    self.tracker.log("[REVIEW-LANG] Khong thay chip English de xoa (co the da OK)", "info")

                # BUOC 5: Save/Back ve Review
                time.sleep(1.5)
                saved = False
                for btn_text in ("Save", "Done", "Update", "Apply"):
                    try:
                        for b in d.find_elements(By.XPATH, "//material-button | //button"):
                            if b.is_displayed() and b.text.strip() == btn_text:
                                _safe_click(b)
                                self.tracker.log(f"[REVIEW-LANG] Click {btn_text} -> ve Review")
                                time.sleep(5)
                                saved = True
                                break
                        if saved:
                            break
                    except Exception:
                        pass
                if not saved:
                    self.tracker.log("[REVIEW-LANG] Khong tim thay Save/Done — co the trang khong can Save", "warn")
                return True

            def _fix_name_duplicate(camp_name_base, camp_idx):
                """Fix name duplicate: tim input name tren Review, tang suffix a1->a2->...->a99."""
                for try_idx in range(camp_idx + 1, camp_idx + 30):
                    # Tim input name
                    name_inp = None
                    for xp in (
                        "//input[@aria-label='Campaign name']",
                        "//input[contains(@aria-label, 'ampaign name')]",
                        "//*[contains(text(), 'Campaign name')]/following::input[1]",
                    ):
                        try:
                            for el in d.find_elements(By.XPATH, xp):
                                if el.is_displayed():
                                    name_inp = el
                                    break
                            if name_inp is not None:
                                break
                        except Exception:
                            pass
                    if name_inp is None:
                        self.tracker.log("[REVIEW] Khong tim thay input name de fix duplicate", "warn")
                        return False

                    new_name = f"{camp_name_base} {try_idx}"
                    try:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'})", name_inp)
                        time.sleep(0.5)
                        clear_and_type(name_inp, new_name)
                        # Enter de Google Ads xac nhan name moi (commit input)
                        try:
                            name_inp.send_keys(Keys.RETURN)
                            self.tracker.log(f"[REVIEW] Doi name: {new_name} + Enter")
                        except Exception:
                            self.tracker.log(f"[REVIEW] Doi name: {new_name} (Enter fail, van tiep)")
                        time.sleep(2.5)  # cho Google validate name
                    except Exception as _e:
                        self.tracker.log(f"[REVIEW] Loi type name: {_e}", "warn")
                        continue

                    # Check con loi duplicate khong
                    still_dup = False
                    try:
                        for el in d.find_elements(By.XPATH, "//*[contains(text(), 'already exists')]"):
                            if el.is_displayed():
                                still_dup = True
                                break
                    except Exception:
                        pass
                    if not still_dup:
                        self.tracker.log(f"[REVIEW] Name OK: {new_name}", "success")
                        return True
                self.tracker.log("[REVIEW] Khong fix duoc name duplicate sau 30 lan", "error")
                return False

            def _fix_networks_from_review():
                """Click Edit ben section Networks -> untick -> Save -> back Review."""
                # Tim button Edit gan 'Networks'
                edit_clicked = False
                for xp in (
                    "//*[contains(normalize-space(.), 'Networks')]/following::*[self::material-button or self::button][contains(translate(., 'EDIT', 'edit'), 'edit')][1]",
                    "//*[contains(normalize-space(.), 'Networks')]/ancestor::*[self::section or self::div][1]//material-button[contains(translate(., 'EDIT', 'edit'), 'edit')]",
                    "//*[contains(normalize-space(.), 'Networks')]/ancestor::*[self::section or self::div][1]//*[@aria-label='Edit']",
                ):
                    try:
                        for el in d.find_elements(By.XPATH, xp):
                            if el.is_displayed():
                                if _safe_click(el):
                                    edit_clicked = True
                                    self.tracker.log("[REVIEW] Da click Edit Networks")
                                    time.sleep(4)
                                    break
                        if edit_clicked:
                            break
                    except Exception:
                        pass
                if not edit_clicked:
                    self.tracker.log("[REVIEW] Khong tim duoc nut Edit Networks", "warn")
                    return False

                # Untick search-checkbox + display-checkbox
                for cls_name in ("search-checkbox", "display-checkbox"):
                    try:
                        for c in _visible(d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls_name}')]")):
                            if is_checkbox_ticked(c):
                                _safe_click(c)
                                self.tracker.log(f"[REVIEW] Da untick {cls_name}", "success")
                                time.sleep(0.8)
                    except Exception:
                        pass
                try:
                    if untick_by_label("Search Partners"):
                        self.tracker.log("[REVIEW] Untick Search Partners (text)")
                    if untick_by_label("Display Network"):
                        self.tracker.log("[REVIEW] Untick Display Network (text)")
                except Exception:
                    pass

                # Click Done/Save/Next de quay lai Review
                for btn_text in ("Done", "Save", "Update", "Apply"):
                    try:
                        for b in d.find_elements(By.XPATH, "//material-button | //button"):
                            if b.is_displayed() and b.text.strip() == btn_text:
                                _safe_click(b)
                                self.tracker.log(f"[REVIEW] Click {btn_text}")
                                time.sleep(4)
                                return True
                    except Exception:
                        pass
                return False

            # Thuc thi validate + fix
            self.tracker.log("[REVIEW] Scan trang Review tim loi...")
            base_name = campaign_config.get("name", "Campaign")
            rv_errors = _scan_review_errors()
            self.tracker.log(f"[REVIEW] name_dup={rv_errors['name_dup']} networks='{rv_errors['networks_text'][:50]}' bidding='{rv_errors['bidding_text'][:50]}' lang_bad={rv_errors['languages_bad']}")

            if rv_errors["name_dup"]:
                _fix_name_duplicate(base_name, camp_index)

            if rv_errors["networks_text"] and ("Search partners" in rv_errors["networks_text"] or "Display Network" in rv_errors["networks_text"]):
                self.tracker.log(f"[REVIEW] Networks con tick: {rv_errors['networks_text']}", "warn")
                _fix_networks_from_review()
                time.sleep(2)
                # Re-scan name duplicate sau khi back
                rv_errors2 = _scan_review_errors()
                if rv_errors2["name_dup"]:
                    _fix_name_duplicate(base_name, camp_index + 1)

            # Languages "Item not found" — click red -> Settings -> F5 -> fix -> back
            if rv_errors["languages_bad"]:
                self.tracker.log("[REVIEW] Languages bao do 'Item not found' -> fix qua Settings", "warn")
                for lang_fix_try in range(3):
                    if not _fix_languages_from_review():
                        break
                    time.sleep(2)
                    rv_errors_l = _scan_review_errors()
                    if not rv_errors_l["languages_bad"]:
                        self.tracker.log(f"[REVIEW] Languages OK sau fix lan {lang_fix_try+1}", "success")
                        break
                    self.tracker.log(f"[REVIEW] Languages van bao do (lan {lang_fix_try+1}) -> retry", "warn")

            expected_bid = (campaign_config.get("bidding") or "").lower()
            actual_bid = rv_errors["bidding_text"].lower()
            if "click" in expected_bid and "click" not in actual_bid and actual_bid:
                self.tracker.log(f"[REVIEW] BIDDING SAI: expect clicks, got '{rv_errors['bidding_text']}'", "error")

            if rv_errors["red_errors"]:
                for err in rv_errors["red_errors"][:5]:
                    self.tracker.log(f"[REVIEW] Red error: {err}", "warn")

            # Click Publish (retry 5 lan — xu ly Fix errors dialog neu co)
            # Trang Review co 2 nut "Publish campaign" (top-right + bottom-right) — uu tien top, fallback bottom
            def _find_publish_btns():
                """Tra ve list tat ca nut Publish visible + enabled (theo thu tu doc trong DOM: top truoc, bottom sau)."""
                btns = []
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    try:
                        if not b.is_displayed() or "Publish campaign" not in b.text:
                            continue
                        if b.get_attribute("aria-disabled") == "true" or not b.is_enabled():
                            continue
                        btns.append(b)
                    except Exception:
                        pass
                return btns

            def _find_publish_btn():
                btns = _find_publish_btns()
                return btns[0] if btns else None

            def _on_review_page():
                # Con o Review khi title co "New campaign"/"Search campaign" HOAC van thay button Publish
                try:
                    t = (d.title or "")
                    if "New campaign" in t or "Search campaign" in t:
                        return True
                except Exception:
                    pass
                return _find_publish_btn() is not None

            for attempt in range(5):
                # 1. Xu ly 2FA / popup / Fix errors TRUOC khi tim Publish
                check_all()

                # 2. Tim TAT CA nut Publish (top + bottom)
                pub_btns = _find_publish_btns()
                if not pub_btns:
                    # Khong thay Publish nao — da roi Review chua?
                    if not _on_review_page():
                        self.tracker.log("[PUBLISH] Da roi trang Review — xong", "success")
                        break
                    self.tracker.log(f"[PUBLISH] Khong tim thay Publish enabled (lan {attempt + 1}) — thu Next", "warn")
                    click_button("Next")
                    time.sleep(5)
                    continue

                # 3. Click lan luot: top truoc, neu fail thi bottom
                click_ok = False
                for idx, pub_btn in enumerate(pub_btns):
                    pos_label = "top" if idx == 0 else ("bottom" if idx == len(pub_btns) - 1 else f"#{idx+1}")
                    try:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'})", pub_btn)
                        time.sleep(1)
                        action_click(pub_btn)
                        self.tracker.log(f"Da click Publish ({pos_label})! (lan {attempt + 1})", "success")
                        time.sleep(3)
                        click_ok = True
                        break
                    except Exception as _ce:
                        self.tracker.log(f"[PUBLISH] Loi click nut {pos_label}: {_ce} — thu nut tiep theo", "warn")
                        time.sleep(1)
                        continue

                if not click_ok:
                    self.tracker.log(f"[PUBLISH] Tat ca nut Publish deu fail (lan {attempt + 1})", "warn")
                    time.sleep(3)
                    continue

                # 4. Wait 25s: xu ly 2FA dang popup + dialog 'cannot run ads' + cho page transition
                deadline_pub = time.time() + 25
                while time.time() < deadline_pub:
                    # Giai 2FA neu pop
                    check_all()

                    # Dialog 'cannot run ads' / 'missing information' -> click Publish trong dialog
                    try:
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
                                                time.sleep(3)
                                                break
                                        except Exception:
                                            pass
                                    break
                            except Exception:
                                pass
                    except Exception as _dl:
                        self.tracker.log(f"[PUBLISH] Loi scan dialog: {_dl}", "warn")

                    # Da roi Review?
                    if not _on_review_page():
                        break
                    time.sleep(2)

                # 5. Check ket qua
                if not _on_review_page():
                    self.tracker.log("[PUBLISH] Da roi trang Review — xong", "success")
                    break
                # Con o Review -> 2FA reset / validate fail -> retry
                self.tracker.log(f"Van o trang Review sau click (lan {attempt + 1}) — retry", "warn")
                time.sleep(3)

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
